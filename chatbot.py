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

            # AI 답변 생성
            # prompt = f"""
            # 당신은 IT 시스템 장애 대응 전문가입니다. 아래 정보를 바탕으로 정확하고 실행 가능한 대응 방안을 제시해주세요.

            # ## 사용자 질의
            # {user_query}

            # ## 관련 장애 사례 분석
            # {context}

            # ## 답변 지침
            # - 샘플 답변을 참고하여 잘바꿈, 들여쓰기를 반드시 출력형식에 반영하세요.  
            # - 벡터스토어의 구조화된 정보를 최대한 활용하세요
            # - 장애 유형(incident_type)별 특화된 대응법을 고려하세요
            # - 근본 원인(root_cause)과 긴급 대응 조치(emergency_actions)를 구분해서 제시하세요
            # - 유사도가 높은 사례 순으로 우선순위를 매기세요
            # - 검색된 사례 개수 만큼만 출력하세요. 
            # - 검색된 유사 사례가 1건도 없는 경우에만 '유사한 오류 사례가 없습니다.'로 답변하세요.  
            # - [유사 사례 제목], [장애 요약], [장애 원인], [대응 방법], [장애보고서]는 항목이고 내용은 반드시 다음 라인에 출력하세요.
            # - [가장 가능성 높은 원인], [두 번째 가능성], [세 번째 가능성] 도 반드시 줄을 구분하여 출력하세요.
            # - summary, root_cause, emergency_actions는 사람이 읽기 쉽게 포매팅하여 작성하세요.
            # - 장애보고서는 웹에서 다운로드 링크되게 작성하세요. 
               

            # ## 요구 출력 형식

            # #### **오류/이상징후 사례**등
  
            # ##### **1. 사례 제목**  
            #    - 장애 유형 : 
            #    - [가장 가능성 높은 원인] 
            #    - [두 번째 가능성] 
            #    - [세 번째 가능성]

            # ##### **2. 사례 제목** 
            #    - [가장 가능성 높은 원인]
            #    - [두 번째 가능성]
            #    - [세 번째 가능성]

            # #### 📚 **참고 사례** (유사도 순)
            # ##### 1. [가장 가능성 높은 유사 사례 제목]
            #    - [장애 요약] : 1번 사례 summary
            #    - [장애 원인] : 1번 사례 root_cause
            #    - [대응 방법] : 1번 사례 emergency_actions
            #    - [장애보고서] : 1번 사례 file_path 
            # ---   
            # ##### 2. [두번째 가능성 높은 유사 사례 제목]
            #    - [장애 요약] : 2번 사례 summary
            #    - [장애 원인] : 2번 사례 root_cause
            #    - [대응 방법] : 2번 사례 emergency_actions
            #    - [장애보고서] : 2번 사례 file_path 


            # ## 샘플 답변     

            # 오류/이상징후 사례         
            # 1. 온누리 상품권 앱 접속 및 충전 불가
            #    - 장애 유형 : 웹방화벽 과부하
            #    - 원인 :
            #       - 웹방화벽(vWAF)의 Burst Traffic으로 인한 과부하
            #       - 프로모션으로 인한 비정상적인 트래픽 증가
            #       - 가용성 모니터링 미흡

            # 참고 사례 (유사도 순)
            # 1. 온누리 상품권 앱 접속 및 충전 불가
            #    - [장애 요약] : 
            #       온누리 상품권 앱의 장애는 웹방화벽(vWAF)의 과부하로 인해 발생하였으며, 긴급조치로 보안정책 변경 및 Scale-up이 이루어졌다. 
            #       향후 유사 장애 예방을 위해 웹방화벽 리소스 모니터링 체계 구축 및 SOP 절차 강화가 필요함.

            #    - [장애 원인] : 
            #       온누리 상품권 앱 접속 시 에러 페이지가 노출되며, 충전 및 결제 기능은 정상적으로 작동함. 
            #       장애의 근본 원인은 15% 할인 프로모션으로 인해 웹방화벽(vWAF)에 발생한 Burst Traffic으로, 
            #       평소 트래픽이 4050M인 반면 프로모션 기간 동안 400500M로 증가하여 웹방화벽의 권장 트래픽을 초과함. 
            #       또한, 웹방화벽의 가용성 모니터링이 미흡하여 장애 발생 전 이상징후를 인지하지 못함.

            #    - [대응 방법] : 
            #       장애 발생 후 웹방화벽(vWAF) 보안정책을 변경하여 차단 메시지 발생 대상을 탐지 모드로 전환하고, 
            #       정책을 전체 탐지로 변경한 후에도 차단 페이지가 지속되어 보안정책을 비활성화하여 문제를 해결함. 
            #       이후, 웹방화벽의 긴급 Scale-up을 통해 안정적인 서비스 제공을 위한 조치를 취함.

            #    - [장애보고서] : 다운로드 링크     
            # """

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
