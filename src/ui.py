"""Giao diện Streamlit để trình diễn Baseline Chatbot và ReAct Agent."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import load_test_cases, run_baseline_chatbot, run_react_agent
from providers import get_llm_provider
from tools import AVAILABLE_TOOLS, _reset_mock_state


st.set_page_config(
    page_title="OrderCare Agent Lab",
    page_icon="📦",
    layout="wide",
)


@st.cache_resource
def get_provider():
    return get_llm_provider()


def run_without_console_output(function, *args):
    """Chạy core function và giữ log console khỏi giao diện Streamlit."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = function(*args)
    return result


def observation_badge(observation: str) -> tuple[str, str, dict[str, Any] | None]:
    try:
        data = json.loads(observation)
    except (json.JSONDecodeError, TypeError):
        return "⚪", "NON_JSON", None
    icon = "🟢" if data.get("ok") else "🔴"
    return icon, str(data.get("code", "UNKNOWN")), data


def render_trace(trace: list[dict[str, Any]]) -> None:
    st.subheader("Agent trace")
    if not trace:
        st.info("Không có tool trace trong lượt này.")
        return

    for index, entry in enumerate(trace, start=1):
        action = entry.get("action")
        observation = entry.get("observation")
        final_answer = entry.get("final_answer")

        if action and observation:
            icon, code, observation_data = observation_badge(observation)
            title = f"{icon} Bước {index}: {action.split('[', 1)[0]} · {code}"
        elif final_answer:
            title = f"🏁 Bước {index}: Final Answer"
            observation_data = None
        else:
            title = f"🛡️ Bước {index}: Guardrail / format check"
            observation_data = None

        with st.expander(title, expanded=bool(action)):
            response = entry.get("response")
            if response:
                st.markdown("**LLM response**")
                st.code(response, language="text")
            if action:
                st.markdown("**Action được hệ thống chấp nhận**")
                st.code(action, language="text")
            if observation:
                st.markdown("**Observation thật từ tool/guardrail**")
                if observation_data is not None:
                    st.json(observation_data)
                else:
                    st.code(observation, language="text")


def render_header(provider) -> None:
    st.title("📦 OrderCare Agent Lab")
    st.caption(
        "Trợ lý tra cứu đơn hàng và xử lý đổi/trả · "
        "Baseline Chatbot vs ReAct Agent"
    )

    provider_name = provider.__class__.__name__
    model_name = getattr(provider, "model_name", "Offline Mock")
    first, second, third = st.columns(3)
    first.metric("LLM Provider", provider_name)
    second.metric("Model", model_name)
    third.metric("Registered tools", len(AVAILABLE_TOOLS))

    st.info(
        "Dữ liệu đơn hàng là mock data phục vụ bài lab. "
        "Baseline không gọi tool; ReAct Agent được phép truy cập mock data."
    )


def initialize_state() -> None:
    st.session_state.setdefault("last_query", "")
    st.session_state.setdefault("baseline_answer", None)
    st.session_state.setdefault("agent_result", None)


def main() -> None:
    initialize_state()
    provider = get_provider()
    tests = load_test_cases()
    render_header(provider)

    with st.sidebar:
        st.header("Thiết lập phiên")
        mode = st.radio(
            "Chế độ",
            ("Baseline Chatbot", "ReAct Agent", "So sánh hai chế độ"),
        )
        source = st.radio(
            "Nguồn câu hỏi",
            ("Nhập tự do", "Test case có sẵn"),
        )

        if source == "Test case có sẵn":
            selected_test = st.selectbox(
                "Chọn test case",
                tests,
                format_func=lambda test: (
                    f"#{test['id']} · {test['category']}"
                ),
            )
            st.caption(selected_test["question"])
        else:
            selected_test = None

        if st.button("Reset mock state", use_container_width=True):
            _reset_mock_state()
            st.session_state.baseline_answer = None
            st.session_state.agent_result = None
            st.success("Đã xóa các yêu cầu đổi/trả phát sinh trong phiên.")

        st.divider()
        st.markdown("**Tools**")
        for tool_name in AVAILABLE_TOOLS:
            st.code(tool_name, language=None)

    with st.form("agent_request", clear_on_submit=False):
        if selected_test is None:
            query = st.text_area(
                "Yêu cầu của khách hàng",
                value=st.session_state.last_query,
                height=130,
                placeholder=(
                    "Ví dụ: Kiểm tra đơn ORD-1001 với mã xác minh VC-01..."
                ),
            )
        else:
            query = selected_test["question"]
            st.text_area(
                "Yêu cầu của khách hàng",
                value=query,
                height=130,
                disabled=True,
            )

        submitted = st.form_submit_button(
            "Chạy trợ lý",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not query.strip():
            st.warning("Vui lòng nhập câu hỏi trước khi chạy.")
        else:
            st.session_state.last_query = query.strip()
            st.session_state.baseline_answer = None
            st.session_state.agent_result = None

            with st.spinner("Đang xử lý yêu cầu..."):
                if mode in {"Baseline Chatbot", "So sánh hai chế độ"}:
                    st.session_state.baseline_answer = run_without_console_output(
                        run_baseline_chatbot,
                        query,
                        provider,
                    )
                if mode in {"ReAct Agent", "So sánh hai chế độ"}:
                    st.session_state.agent_result = run_without_console_output(
                        run_react_agent,
                        query,
                        provider,
                    )

    baseline_answer = st.session_state.baseline_answer
    agent_result = st.session_state.agent_result

    if baseline_answer is not None and agent_result is not None:
        baseline_column, agent_column = st.columns(2)
        with baseline_column:
            st.subheader("💬 Baseline Chatbot")
            st.markdown(baseline_answer)
        with agent_column:
            st.subheader("🤖 ReAct Agent")
            st.markdown(agent_result["final_answer"])
            st.caption(f"Trạng thái: {agent_result['status']}")
        render_trace(agent_result["trace"])
    elif baseline_answer is not None:
        st.subheader("💬 Baseline Chatbot")
        st.markdown(baseline_answer)
        st.caption("Không có tool call trong chế độ Baseline.")
    elif agent_result is not None:
        st.subheader("🤖 ReAct Agent")
        st.markdown(agent_result["final_answer"])
        st.caption(f"Trạng thái: {agent_result['status']}")
        render_trace(agent_result["trace"])


if __name__ == "__main__":
    main()
