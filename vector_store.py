import os
import base64
from datetime import datetime, timezone, timedelta
import uuid
from typing import List, Dict, Any
from azure_client import AzureClients
from document_processor import DocumentProcessor
from urllib.parse import urlparse, quote, unquote
from azure.storage.blob import generate_blob_sas, BlobSasPermissions


class VectorStore:
    def __init__(self, azure_clients: AzureClients, doc_processor: DocumentProcessor):
        self.azure_clients = azure_clients
        self.doc_processor = doc_processor
        self.search_client = azure_clients.search_client

    def add_document(self, file_path: str, title: str, file_type: str) -> bool:
        """문서를 벡터 스토어에 추가 (동일 title 존재 시 기존 데이터 삭제 후 추가)"""
        try:
            # 기존 동일 title 문서 삭제
            existing_docs = self.search_client.search(
                search_text="*", select=["id", "title"]
            )

            ids_to_delete = [
                doc["id"] for doc in existing_docs if doc["title"] == title
            ]
            if ids_to_delete:
                self.search_client.delete_documents(
                    [{"id": id_} for id_ in ids_to_delete]
                )
                print(f"기존 '{title}' 문서 {len(ids_to_delete)}건 삭제")

            # 텍스트 추출
            content = self.doc_processor.extract_text_from_file(file_path, file_type)
            if not content:
                return False

            # 문서 분석
            analysis = self.doc_processor.analyze_incident_report(content)

            # 전체 텍스트에 대한 임베딩 생성
            full_text = f"{title}\n{content}\n{analysis['document_summary']}"
            embedding = self.doc_processor.generate_embedding(full_text)

            if not embedding:
                return False

            # Blob Storage에 업로드
            blob_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{title}"
            blob_url = self.doc_processor.upload_to_blob_storage(file_path, blob_name)

            KST = timezone(timedelta(hours=9))
            # 검색 인덱스에 문서 추가
            document = {
                "id": str(uuid.uuid4()),
                "title": title,
                "content": content,
                "summary": analysis["document_summary"],
                "incident_type": self._extract_incident_type(content),
                "root_cause": analysis["incident_symptoms_and_causes"],
                "emergency_actions": analysis["emergency_actions"],
                "content_vector": embedding,
                "file_path": blob_url,
                "upload_date": datetime.now(KST).isoformat(),
            }

            self.search_client.upload_documents([document])
            return True

        except Exception as e:
            print(f"문서 추가 중 오류: {e}")
            return False

    def _extract_incident_type(self, content: str) -> str:
        """장애 유형 추출"""
        content_lower = content.lower()

        if any(word in content_lower for word in ["네트워크", "network", "통신"]):
            return "네트워크 장애"
        elif any(word in content_lower for word in ["데이터베이스", "database", "db"]):
            return "데이터베이스 장애"
        elif any(word in content_lower for word in ["서버", "server", "시스템"]):
            return "시스템 장애"
        elif any(word in content_lower for word in ["방화벽", "firewall", "보안"]):
            return "보안 장애"
        elif any(word in content_lower for word in ["앱", "app", "애플리케이션"]):
            return "애플리케이션 장애"
        else:
            return "기타"

    def _generate_sas_url(self, blob_url: str) -> str:
        """Generate SAS URL for blob access"""
        try:
            # blob_url에서 container와 blob_name 추출
            parsed_url = urlparse(blob_url)
            path_parts = parsed_url.path.lstrip("/").split("/")

            # 첫 번째 부분은 container_name
            container_name = path_parts[0]
            # 나머지 부분들을 blob_name으로 조합하고 URL 디코딩
            blob_name = unquote("/".join(path_parts[1:]))
            account_name = parsed_url.hostname.split(".")[0]

            # 디버깅을 위한 로그
            print(f"Container: {container_name}")
            print(f"Blob name: {blob_name}")
            print(f"Account: {account_name}")

            # SAS 토큰 생성 (1시간 유효)
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=self.azure_clients.config.AZURE_STORAGE_KEY,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1),
            )

            # URL 생성 - blob_name은 이미 디코딩되어 있으므로 다시 인코딩
            encoded_blob_name = quote(blob_name, safe="")
            base_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{encoded_blob_name}"
            return f"{base_url}?{sas_token}"

        except Exception as e:
            print(f"SAS URL 생성 중 오류: {e}")
            print(f"Original URL: {blob_url}")
            return blob_url

    def search_similar_documents(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """유사한 문서 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.doc_processor.generate_embedding(query)
            if not query_embedding:
                return []

            # 벡터 검색 수행
            results = self.search_client.search(
                search_text=query,
                vector_queries=[
                    {
                        "vector": query_embedding,
                        "k_nearest_neighbors": top_k,
                        "fields": "content_vector",
                        "kind": "vector",
                    }
                ],
                select=[
                    "id",
                    "title",
                    "incident_type",
                    "content",
                    "summary",
                    "root_cause",
                    "emergency_actions",
                    "file_path",
                    "upload_date",
                ],
                top=top_k,
            )

            # 검색 결과를 리스트로 변환하고 SAS URL 생성
            search_results = []
            for result in results:
                result_dict = dict(result)
                if result_dict.get("file_path"):
                    result_dict["file_path"] = self._generate_sas_url(
                        result_dict["file_path"]
                    )
                search_results.append(result_dict)

            return search_results

        except Exception as e:
            print(f"검색 중 오류: {e}")
            return []

    def index_docx_to_azure_ai_search(self, file_path: str, title: str):
        """DOCX 문서를 Azure AI Search에 기본 임베딩/청킹 옵션으로 인덱싱"""
        try:
            # 텍스트 추출
            content = self.doc_processor.extract_text_from_file(file_path, "docx")
            if not content:
                print("문서에서 텍스트를 추출하지 못했습니다.")
                return False

            # 기존 동일 title 문서 삭제
            existing_docs = self.search_client.search(
                search_text="*", select=["id", "title"]
            )
            ids_to_delete = [
                doc["id"] for doc in existing_docs if doc["title"] == title
            ]
            if ids_to_delete:
                self.search_client.delete_documents(
                    [{"id": id_} for id_ in ids_to_delete]
                )
                print(f"기존 '{title}' 문서 {len(ids_to_delete)}건 삭제")

            # Azure AI Search의 기본 임베딩/청킹 사용 (여기서는 단일 문서로 업로드)
            document = {
                "id": str(uuid.uuid4()),
                "title": title,
                "content": content,
                "upload_date": datetime.now(timezone(timedelta(hours=9))).isoformat(),
            }
            self.search_client.upload_documents([document])
            print(f"DOCX 문서 '{title}'가 Azure AI Search에 인덱싱되었습니다.")
            return True
        except Exception as e:
            print(f"DOCX 인덱싱 중 오류: {e}")
            return False
