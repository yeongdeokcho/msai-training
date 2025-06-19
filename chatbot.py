from typing import List, Dict, Any
from config import Config
from azure_client import AzureClients
from vector_store import VectorStore
from document_processor import DocumentProcessor
from datetime import datetime, timezone, timedelta


class IncidentChatbot:
    def __init__(self, azure_clients: AzureClients, vector_store: VectorStore):
        self.azure_clients = azure_clients
        self.vector_store = vector_store
        self.openai_client = azure_clients.openai_client

    def answer_query(self, user_query: str) -> Dict[str, Any]:
        """사용자 질의에 대한 답변 생성"""
        try:
            # 유사한 장애 사례 검색
            similar_docs = self.vector_store.search_similar_documents(
                user_query, top_k=3
            )

            if not similar_docs:
                return {
                    "answer": "관련된 장애 사례를 찾을 수 없습니다.",
                    "related_documents": [],
                    "confidence": 0.0,
                }

            # 컨텍스트 구성
            context = self._build_context(similar_docs)        
            prompt = f"""
              당신은 IT 시스템 장애 대응 전문가입니다. 아래 정보를 바탕으로 정확하고 실행 가능한 대응 방안을 제시해주세요.

              ## 사용자 질의
              {user_query}

              ## 관련 장애 사례 분석
              {context}

              ## 중요한 답변 규칙
              - **context에 장애 사례가 포함되어 있으면 반드시 해당 사례들을 분석하여 답변하세요**
              - **context가 완전히 비어있는 경우에만 "유사한 장애 사례를 찾을 수 없습니다"라고 답변하세요**
              - **절대로 검색된 사례가 있는데 "유사 사례 없음"이라고 답변하지 마세요**
              - **[장애 요약], [장애 원인], [대응 방법], [장애보고서] 등의 항목명은 반드시 그 다음 줄에 내용을 작성하세요**
              - **검색된 사례 개수만큼 순서대로 모두 출력하세요**

              ## 답변 지침
              - 벡터스토어의 구조화된 정보(incident_type, summary, root_cause, emergency_actions)를 최대한 활용하세요
              - 장애 유형별 특화된 대응법을 고려하세요
              - 근본 원인과 긴급 대응 조치를 명확히 구분하세요
              - 유사도가 높은 사례 순으로 우선순위를 매기세요
              - summary, root_cause, emergency_actions는 사람이 읽기 쉽게 포매팅하여 작성하세요
              - 장애보고서는 [다운로드 링크]({{file_path}})로 링크 형태로 작성하세요

              ## 요구 출력 형식

              #### **오류/이상징후 사례**

              ##### **1. {{첫 번째 사례의 title}}**
              - **장애 유형**: {{첫 번째 사례의 incident_type}}
              - **원인**:
                - {{첫 번째 사례 root_cause에서 추출한 주요 원인 1}}
                - {{첫 번째 사례 root_cause에서 추출한 주요 원인 2}}
                - {{첫 번째 사례 root_cause에서 추출한 주요 원인 3}}

              ##### **2. {{두 번째 사례의 title}}** (두 번째 사례가 있는 경우)
              - **장애 유형**: {{두 번째 사례의 incident_type}}
              - **원인**:
                - {{두 번째 사례 root_cause에서 추출한 주요 원인 1}}
                - {{두 번째 사례 root_cause에서 추출한 주요 원인 2}}
                - {{두 번째 사례 root_cause에서 추출한 주요 원인 3}}

              #### 📚 **참고 사례** (유사도 순)

              ##### 1. {{첫 번째 사례의 title}}
              - **[장애 요약]**:  
                {{첫 번째 사례의 summary를 읽기 쉽게 포매팅}}

              - **[장애 원인]**:  
                {{첫 번째 사례의 root_cause를 읽기 쉽게 포매팅}}

              - **[대응 방법]**:  
                {{첫 번째 사례의 emergency_actions를 읽기 쉽게 포매팅}}

              - **[장애보고서]**: [다운로드 링크]({{첫 번째 사례의 file_path}})

              ---

              ##### 2. {{두 번째 사례의 title}} (두 번째 사례가 있는 경우)
              - **[장애 요약]**:  
                {{두 번째 사례의 summary를 읽기 쉽게 포매팅}}

              - **[장애 원인]**:  
                {{두 번째 사례의 root_cause를 읽기 쉽게 포매팅}}

              - **[대응 방법]**:  
                {{두 번째 사례의 emergency_actions를 읽기 쉽게 포매팅}}

              - **[장애보고서]**: [다운로드 링크]({{두 번째 사례의 file_path}})

              ---

              ## 예외 상황 (context가 완전히 비어있는 경우에만 사용)
              유사한 장애 사례를 찾을 수 없습니다.

              **일반적인 장애 대응 절차를 안내해드리겠습니다:**
              1. 장애 현상 파악 및 상세 기록
              2. 관련 시스템 로그 및 모니터링 지표 확인  
              3. 네트워크, 서버, 데이터베이스 상태 점검
              4. 관련 팀에 상황 공유 및 에스컬레이션
              5. 임시 우회 방안 검토 및 적용

              """

            # AI 답변 생성

            response = self.openai_client.chat.completions.create(
                model=self.azure_clients.config.AZURE_OPENAI_CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 IT 장애 대응 전문가입니다. 과거 장애 사례를 바탕으로 정확하고 실용적인 조언을 제공합니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content

            return {
                "answer": answer,
                "related_documents": similar_docs,
            }

        except Exception as e:
            print(f"답변 생성 중 오류: {e}")
            return {
                "answer": "답변 생성 중 오류가 발생했습니다.",
                "related_documents": [],
                "confidence": 0.0,
            }

    def _build_context(self, documents: List[Dict[str, Any]]) -> str:
        """문서들로부터 컨텍스트 구성"""
        context_parts = []

        for i, doc in enumerate(documents, 1):
            context_part = f"""
                        사례 {i}: {doc.get('title', '제목 없음')}
                        - 원인: {doc.get('root_cause', '정보 없음')}
                        - 대응방안: {doc.get('emergency_actions', '정보 없음')}
                        - 요약: {doc.get('summary', '정보 없음')}
                        - 장애보고서: {doc.get('file_path', '정보 없음')}
                """
            context_parts.append(context_part)

        return "\n".join(context_parts)

if __name__ == "__main__":

    config = Config()
    azure_clients = AzureClients(config)
    doc_processor = DocumentProcessor(azure_clients)
    vector_store = VectorStore(azure_clients, doc_processor)
    chatbot = IncidentChatbot(azure_clients, vector_store)

    message = "장애"
    result = chatbot.answer_query(message)
    print(result)
