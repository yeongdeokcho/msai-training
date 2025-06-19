import re
from datetime import datetime
from typing import Dict, List
import docx
import PyPDF2
from config import Config
from azure_client import AzureClients
from azure.storage.blob import BlobServiceClient
from azure_client import AzureClients
import json


class DocumentProcessor:
    def __init__(self, azure_clients: AzureClients):
        self.azure_clients = azure_clients
        self.openai_client = azure_clients.openai_client

    def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """파일에서 텍스트 추출"""
        try:
            if file_type == "docx":
                return self._extract_from_docx(file_path)
            elif file_type == "pdf":
                return self._extract_from_pdf(file_path)
            elif file_type in ["txt", "md"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"텍스트 추출 중 오류: {e}")
            return ""

    def _extract_from_docx(self, file_path: str) -> str:
        """DOCX 파일에서 텍스트 추출"""
        doc = docx.Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return "\n".join(text)

    def _extract_from_pdf(self, file_path: str) -> str:
        """PDF 파일에서 텍스트 추출"""
        text = []
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text.append(page.extract_text())
        return "\n".join(text)

    def analyze_incident_report(self, content: str) -> Dict[str, str]:
        """장애보고서 분석 및 4가지 요약 생성"""

        prompt = f"""
다음 장애보고서를 분석하여 아래 4가지 항목으로 요약해주세요:

1. 장애 현상과 원인
2. 긴급조치 방안
3. 문서 전체 요약
4. 이미지 및 차트 설명 (문서에 포함된 이미지나 차트가 있다면)

장애보고서 내용:
{content}

출력 형식:
```json
{{
    "incident_symptoms_and_causes": "장애 현상과 근본 원인에 대한 상세 설명",
    "emergency_actions": "긴급조치 방안과 대응 절차",
    "document_summary": "전체 문서의 핵심 내용 요약",
    "image_descriptions": "이미지나 차트에 대한 설명 (없으면 '해당없음')"
}}
```
"""

        try:
            response = self.openai_client.chat.completions.create(
                # model="gpt-4o-mini",
                model=self.azure_clients.config.AZURE_OPENAI_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 장애보고서 분석 전문가입니다. 정확하고 구조화된 분석을 제공합니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            result = response.choices[0].message.content
            # JSON 부분 추출
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            json_str = result[json_start:json_end]

            return json.loads(json_str)

        except Exception as e:
            print(f"문서 분석 중 오류: {e}")
            return {
                "incident_symptoms_and_causes": "분석 실패",
                "emergency_actions": "분석 실패",
                "document_summary": "분석 실패",
                "image_descriptions": "분석 실패",
            }

    def generate_embedding(self, text: str) -> List[float]:
        """텍스트 임베딩 생성"""
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                # model="text-embedding-3-small"
                model=self.azure_clients.config.AZURE_OPENAI_EMBEDDING_MODEL,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"임베딩 생성 중 오류: {e}")
            return []

    def upload_to_blob_storage(self, file_path: str, blob_name: str) -> str:
        """파일을 Blob Storage에 업로드"""
        try:
            blob_client = self.azure_clients.blob_client.get_blob_client(
                container=self.azure_clients.config.AZURE_STORAGE_CONTAINER_NAME,
                blob=blob_name,
            )

            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            return blob_client.url
        except Exception as e:
            print(f"Blob 업로드 중 오류: {e}")
            return ""

    def extract_incident_type(self, content: str) -> str:
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


if __name__ == "__main__":
    # 실제 사용시 AzureClients 객체를 생성해서 넘겨야 함.
    config = Config()
    azure_clients = AzureClients(config)
    doc_processor = DocumentProcessor(azure_clients)

    doc_data = doc_processor._extract_from_docx("data/sample02.docx")

    print(doc_data)
