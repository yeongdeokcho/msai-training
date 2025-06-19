from datetime import datetime, timezone, timedelta
import streamlit as st
import os
import tempfile
from pathlib import Path
import sys


# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import VectorStore
from document_processor import DocumentProcessor
from azure_client import AzureClients
from config import Config

# 페이지 설정
st.set_page_config(page_title="RAG 지식 생성", page_icon="📚", layout="wide")

# 사이드바 가로 사이즈 지정을 위한 css

css = """
    <style>
        section[data-testid="stSidebar"] {
            width: 350px !important; # Set the width to your desired value
        }
        .stButton > button {
            width: 100%;
            margin-top: 10px;
        }
    </style>
"""
st.markdown(css, unsafe_allow_html=True)

# 페이지 제목
st.title("📚 RAG 지식 생성")


def init_session_state():
    """세션 상태 초기화"""
    if "uploaded_files" not in st.session_state:
        st.session_state["uploaded_files"] = []
    if "file_contents" not in st.session_state:
        st.session_state["file_contents"] = {}
    if "knowledge_generated" not in st.session_state:
        st.session_state["knowledge_generated"] = False
    if "vector_store" not in st.session_state:
        st.session_state["vector_store"] = None
    if "azure_clients" not in st.session_state:
        st.session_state["azure_clients"] = None
    if "doc_processor" not in st.session_state:
        st.session_state["doc_processor"] = None


def initialize_azure_clients():
    """Azure 클라이언트 초기화"""
    try:
        config = Config()
        azure_clients = AzureClients(config)
        return azure_clients
    except Exception as e:
        st.error(f"Azure 클라이언트 초기화 실패: {str(e)}")
        return None


def process_uploaded_file(uploaded_file, doc_processor):
    """업로드된 파일 처리 - DocumentProcessor 사용"""
    if uploaded_file is None:
        return None

    try:
        # 임시 파일로 저장
        temp_file_path = save_uploaded_file_to_temp(uploaded_file)
        if not temp_file_path:
            return None

        # 파일 확장자 확인
        file_extension = uploaded_file.name.split(".")[-1].lower()

        # DocumentProcessor를 사용하여 텍스트 추출
        content = doc_processor.extract_text_from_file(temp_file_path, file_extension)

        analysis = doc_processor.analyze_incident_report(content)
        KST = timezone(timedelta(hours=9))
        # 검색 인덱스에 문서 추가
        document = {
            "title": (
                ".".join(uploaded_file.name.split(".")[:-1])
                if "." in uploaded_file.name
                else uploaded_file.name
            ),
            "content": content,
            "summary": analysis["document_summary"],
            "incident_type": doc_processor.extract_incident_type(content),
            "root_cause": analysis["incident_symptoms_and_causes"],
            "emergency_actions": analysis["emergency_actions"],
            "upload_date": datetime.now(KST).isoformat(),
        }

        # 임시 파일 삭제
        os.unlink(temp_file_path)

        return document
    except Exception as e:
        st.error(f"파일 처리 중 오류: {str(e)}")
        return None


def save_uploaded_file_to_temp(uploaded_file):
    """업로드된 파일을 임시 파일로 저장"""
    try:
        # 임시 파일 생성
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}"
        )
        temp_file.write(uploaded_file.getvalue())
        temp_file.close()
        return temp_file.name
    except Exception as e:
        st.error(f"파일 저장 중 오류: {str(e)}")
        return None


def generate_knowledge_base():
    """지식베이스 생성 - VectorStore 사용"""
    if not st.session_state["file_contents"]:
        st.error("업로드된 파일이 없습니다.")
        return

    # Azure 클라이언트 초기화
    if st.session_state["azure_clients"] is None:
        st.session_state["azure_clients"] = initialize_azure_clients()
        if st.session_state["azure_clients"] is None:
            return

    # DocumentProcessor 초기화
    if st.session_state["doc_processor"] is None:
        st.session_state["doc_processor"] = DocumentProcessor(
            st.session_state["azure_clients"]
        )

    try:
        # VectorStore 초기화
        vector_store = VectorStore(
            st.session_state["azure_clients"], st.session_state["doc_processor"]
        )
        st.session_state["vector_store"] = vector_store

        success_count = 0
        total_files = len(st.session_state["file_contents"])

        # 각 파일을 벡터 스토어에 추가
        for filename, content in st.session_state["file_contents"].items():
            with st.spinner(f"{filename} 파일을 지식베이스에 추가 중..."):
                # 파일 확장자 확인
                file_extension = filename.split(".")[-1].lower()

                if file_extension not in ["docx", "pdf"]:
                    st.warning(f"{filename}: 지원하지 않는 파일 형식입니다.")
                    continue

                # 임시 파일로 저장
                temp_file_path = save_uploaded_file_to_temp(
                    next(
                        f
                        for f in st.session_state["uploaded_files"]
                        if f.name == filename
                    )
                )

                if temp_file_path:
                    try:
                        # VectorStore의 add_document 함수 사용
                        success = vector_store.add_document(
                            file_path=temp_file_path,
                            title=filename,
                            file_type=file_extension,
                        )

                        if success:
                            success_count += 1

                        # 임시 파일 삭제
                        os.unlink(temp_file_path)

                    except Exception as e:
                        st.error(f"❌ {filename} 처리 중 오류: {str(e)}")
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)

        # 결과 표시
        if success_count > 0:
            st.session_state["knowledge_generated"] = True
            st.success(
                f"✅ 지식베이스 생성 완료! ({success_count}/{total_files} 파일 성공)"
            )

            # 생성된 지식베이스 정보 표시
            total_chars = sum(
                len(content) for content in st.session_state["file_contents"].values()
            )

            st.info(
                f"""
            **생성된 지식베이스 정보:**
            - 성공적으로 처리된 파일 수: {success_count}개
            - 총 텍스트 길이: {total_chars:,}자
            - 성공한 파일 목록: {', '.join([f for f in st.session_state["file_contents"].keys()][:success_count])}
            """
            )
        else:
            st.error("❌ 모든 파일 처리에 실패했습니다.")

    except Exception as e:
        st.error(f"지식베이스 생성 중 오류가 발생했습니다: {str(e)}")


# 세션 상태 초기화
init_session_state()

with st.sidebar:
    st.header("📁 파일 업로드")

    # 파일 업로더
    uploaded_files = st.file_uploader(
        "지식베이스에 추가할 파일을 선택하세요",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        help="DOCX 또는 PDF 파일을 선택하세요",
    )

    # 파일 처리
    if uploaded_files:
        # Azure 클라이언트 초기화 (필요시)
        if st.session_state["azure_clients"] is None:
            st.session_state["azure_clients"] = initialize_azure_clients()

        # DocumentProcessor 초기화 (필요시)
        if (
            st.session_state["azure_clients"]
            and st.session_state["doc_processor"] is None
        ):
            st.session_state["doc_processor"] = DocumentProcessor(
                st.session_state["azure_clients"]
            )

        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state["file_contents"]:
                with st.spinner(f"{uploaded_file.name} 파일을 처리 중..."):
                    content = process_uploaded_file(
                        uploaded_file, st.session_state["doc_processor"]
                    )
                    if content:
                        st.session_state["file_contents"][uploaded_file.name] = content
                        st.session_state["uploaded_files"].append(uploaded_file)

    # 업로드된 파일 목록 표시
    if st.session_state["file_contents"]:
        st.subheader("📋 업로드된 파일 목록")
        for i, filename in enumerate(st.session_state["file_contents"].keys()):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"📄 {filename}")
            with col_b:
                if st.button("삭제", key=f"delete_{i}"):
                    del st.session_state["file_contents"][filename]
                    st.session_state["uploaded_files"] = [
                        f
                        for f in st.session_state["uploaded_files"]
                        if f.name != filename
                    ]
                    st.rerun()

    # 지식데이터 생성 버튼
    st.header("🔧 지식베이스 생성")

    if st.session_state["file_contents"]:
        if st.button(
            "🚀 지식데이터 생성하기", type="primary", use_container_width=True
        ):
            with st.spinner("지식베이스를 생성 중..."):
                generate_knowledge_base()
    else:
        st.info("📁 파일을 업로드한 후 지식데이터를 생성할 수 있습니다.")

    # 생성된 지식베이스 상태 표시
    if st.session_state["knowledge_generated"]:
        st.success("✅ 지식베이스가 준비되었습니다!")

        # 지식베이스 초기화 버튼
        if st.button("🔄 지식베이스 초기화", use_container_width=True):
            st.session_state["uploaded_files"] = []
            st.session_state["file_contents"] = {}
            st.session_state["knowledge_generated"] = False
            st.session_state["vector_store"] = None
            st.rerun()

# 우측 컬럼 - 파일 내용 표시 (col2만 메인에 남김)
col2 = st.container()
with col2:
    st.header("📖 파일 내용")

    if st.session_state["file_contents"]:
        # 파일 선택 드롭다운
        selected_file = st.selectbox(
            "확인할 파일을 선택하세요",
            options=list(st.session_state["file_contents"].keys()),
            index=0,
        )

        if selected_file:
            content = st.session_state["file_contents"][selected_file]

            # 파일 정보 표시
            file_info_col1, file_info_col2 = st.columns(2)
            with file_info_col1:
                st.text(f"파일명: {selected_file}")
            with file_info_col2:
                st.metric("문자 수", f"{len(content['content']):,}")

            # 파일 내용 표시
            value_lines = []
            for k, v in content.items():
                if isinstance(v, str):
                    v_str = v.replace("\\n", "\n")
                else:
                    v_str = str(v)
                value_lines.append(f"[{k}]\n{v_str}\n")
            st.text_area(
                "파일 내용",
                value="".join(value_lines),
                height=600,
                disabled=True,
            )

    else:
        st.info("📁 파일을 업로드하면 내용이 여기에 표시됩니다.")
