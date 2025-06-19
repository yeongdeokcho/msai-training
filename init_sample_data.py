# init_sample_data.py
# 샘플 장애보고서 데이터로 시스템 초기화
import os
from dotenv import load_dotenv
import sys
from config import Config
from azure_client import AzureClients
from document_processor import DocumentProcessor
from vector_store import VectorStore


load_dotenv()

def init_sample_data():
    """샘플 장애보고서로 시스템 초기화"""
    
    print("=== 장애보고서 분석 시스템 초기화 ===")
    
    # 클라이언트 초기화
    config = Config()
    print("=== STEP1 ===")  
    azure_clients = AzureClients(config)   
    print("=== STEP2 ===")   
    doc_processor = DocumentProcessor(azure_clients)
    print("=== STEP3 ===")       
    vector_store = VectorStore(azure_clients, doc_processor)
    print("=== STEP4 ===")   

    # 샘플 장애보고서 데이터
    sample_documents = [
        {
            "title": "온누리 상품권 앱 접속 및 충전 불가",
            "content": """
            [장애 현상]
            - 온누리상품권 앱 접속 시 에러 페이지 노출(부분)
            - 정상 접속 시 충전 기능 정상, 결제는 정상
            - Web firewall Security policy blocked 메시지 발생
            
            [장애 원인]
            - 15% 할인 프로모션으로 인한 Burst Traffic 발생
            - 평시 트래픽 40~50M에서 프로모션 시 400~500M(10배 증가)
            - 웹방화벽(vWAF) 권장 트래픽 100M 초과로 인한 과부화(5배)
            - 웹방화벽 Spec: CPU 2 Core / RAM 4GB, 권장 처리량 100Mbps
            
            [긴급조치]
            1. 웹방화벽 보안정책 변경 - 차단탐지를 탐지모드로 전환
            2. 전체 보안정책 탐지 전환 후에도 차단 지속으로 정책 비활성화
            3. 웹방화벽 Scale-up: 2Core/4GB → 8Core/32GB
            4. 권장 처리량: 100Mbps → 800Mbps로 증설
            
            [후속조치]
            - 프로모션 기간 웹방화벽 모니터링 강화
            - 주요 이벤트 사전 공유 체계 마련
            - 웹방화벽 리소스 모니터링 체계 구축
            """
        },
        {
            "title": "데이터베이스 연결 장애 사례",
            "content": """
            [장애 현상]
            - 애플리케이션에서 데이터베이스 연결 실패
            - Connection timeout 오류 발생
            - 서비스 응답 지연 및 일부 기능 불가
            
            [장애 원인]
            - 데이터베이스 서버 CPU 사용률 100% 지속
            - 대용량 배치 작업으로 인한 Lock 발생
            - Connection Pool 고갈
            
            [긴급조치]
            1. 배치 작업 중단
            2. 데이터베이스 재시작
            3. Connection Pool 설정 증가
            4. 불필요한 쿼리 최적화
            
            [후속조치]
            - 배치 작업 스케줄 조정
            - 데이터베이스 모니터링 강화
            - 쿼리 성능 튜닝
            """
        },
        {
            "title": "네트워크 통신 장애",
            "content": """
            [장애 현상]
            - 외부 API 호출 실패
            - 네트워크 연결 불안정
            - 간헐적 서비스 중단
            
            [장애 원인]
            - 방화벽 정책 변경으로 인한 포트 차단
            - 네트워크 장비 장애
            - DNS 해석 오류
            
            [긴급조치]
            1. 방화벽 정책 롤백
            2. 네트워크 장비 재시작
            3. DNS 설정 확인 및 수정
            4. 우회 경로 설정
            
            [후속조치]
            - 네트워크 변경 사전 검토 프로세스 강화
            - 모니터링 시스템 개선
            - 백업 통신 경로 구축
            """
        }
    ]
    
    # 샘플 문서 추가
    for i, doc_data in enumerate(sample_documents, 1):
        print(f"샘플 문서 {i} 추가 중: {doc_data['title']}")
        
        # 임시 파일 생성
        temp_file = f"temp_sample_{i}.txt"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(doc_data['content'])
        
        # 벡터 스토어에 추가
        print("=== STEP5 ===")   
        success = vector_store.add_document(
            temp_file, 
            doc_data['title'], 
            'txt'
        )
        
        # 임시 파일 삭제
        os.remove(temp_file)
        
        if success:
            print(f"✓ {doc_data['title']} 추가 완료")
        else:
            print(f"✗ {doc_data['title']} 추가 실패")
    
    print("\n=== 초기화 완료 ===")
    print("웹 애플리케이션을 시작할 수 있습니다.")

if __name__ == "__main__":
    init_sample_data()