import streamlit as st
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from chatbot import IncidentChatbot
from azure_client import AzureClients
from vector_store import VectorStore
from document_processor import DocumentProcessor
from config import Config

load_dotenv(override=True)

# 사이드바 가로 사이즈 지정을 위한 css
css = """
<style>
    [data-testid="stSidebar"] {
        width: 350px !important;
        min-width: 350px !important;
        max-width: 350px !important;
        transition: none !important;
        box-sizing: border-box;
    }
    section[data-testid="stSidebar"] {
        width: 350px !important;
        min-width: 350px !important;
        max-width: 350px !important;
        transition: none !important;
        box-sizing: border-box;
    }
    .stButton > button {
        width: 100%;
        margin-top: 10px;
    }
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# streamlit UI 타이틀
st.title("오류/이상징후 조회 챗봇")


def init_session_state():
    """세션 상태 초기화"""

    # streamlit UI 대화이력 저장을 위해 생성
    if "messages" not in st.session_state:
        # 대화기록을 저장하기 위해 생성
        st.session_state["messages"] = []

    # 챗봇 인스턴스 생성 (최초 1회만)
    if "chatbot" not in st.session_state:
        config = Config()
        azure_clients = AzureClients(config)
        doc_processor = DocumentProcessor(azure_clients)
        vector_store = VectorStore(azure_clients, doc_processor)
        st.session_state["chatbot"] = IncidentChatbot(azure_clients, vector_store)


# if clear_btn:
def reset_conversation():
    st.session_state["messages"] = []


# 세션 상태 초기화
init_session_state()


# UI 사이드바 생성
with st.sidebar:
    # 초기화 버튼
    clear_btn = st.button("대화 초기화", type="primary", use_container_width=True)


# 대화 초기화 처리
if clear_btn:
    reset_conversation()

user_input = st.chat_input(
    "안녕하세요, 무엇을 도와드릴까요?",
)

# 사용자의 입력이 있으면 바로 메시지에 추가하고, pending 상태를 추가
if user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    st.session_state["pending"] = True
    st.session_state["pending_question"] = user_input
    st.rerun()

# 메시지 기록이 있으면 모두 표시
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.write(msg["content"])

# pending 상태면 spinner와 함께 빈 assistant 메시지 출력
if st.session_state.get("pending", False):
    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            # 답변 생성
            result = st.session_state["chatbot"].answer_query(
                st.session_state["pending_question"]
            )
            ai_response = result["answer"]
            st.session_state["messages"].append(
                {"role": "assistant", "content": ai_response}
            )
            st.session_state["pending"] = False
            st.session_state["pending_question"] = None
            st.rerun()
