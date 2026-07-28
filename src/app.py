"""Ứng dụng chính ghép LLM, prompts, tools và test cases của nhóm."""

from __future__ import annotations

import ast
import csv
import inspect
import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from prompts import CHATBOT_BASELINE_PROMPT, MAX_ITERATIONS, REACT_SYSTEM_PROMPT
from providers import get_llm_provider
from tools import AVAILABLE_TOOLS

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

ACTION_PATTERN = re.compile(
    r"^\s*Action:\s*([A-Za-z_]\w*)\s*\[(.*)\]\s*$",
    re.MULTILINE,
)
FINAL_PATTERN = re.compile(
    r"Final Answer:\s*(.+)\Z",
    re.DOTALL | re.IGNORECASE,
)
VERIFICATION_CODE_PATTERN = re.compile(r"\bVC-\d+\b", re.IGNORECASE)


def load_test_cases() -> list[dict[str, Any]]:
    """Đọc bộ test cases của Role 1."""
    config_path = os.path.join(PROJECT_DIR, "config", "test_cases.json")
    with open(config_path, "r", encoding="utf-8") as file:
        tests = json.load(file)
    if not isinstance(tests, list):
        raise ValueError("config/test_cases.json phải chứa một JSON array.")
    return tests


def run_baseline_chatbot(user_query: str, provider) -> str:
    """Chạy chatbot baseline không có quyền gọi tool."""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(
        user_query,
        system_prompt=CHATBOT_BASELINE_PROMPT,
    )
    print(f"🤖 Chatbot trả lời:\n{response}")
    return response


def _parse_action_arguments(raw_arguments: str) -> list[Any]:
    """Đọc tham số Action từ cú pháp JSON hoặc Python literal."""
    wrapped = f"[{raw_arguments.strip()}]"
    if wrapped == "[]":
        return []

    try:
        parsed = json.loads(wrapped)
    except json.JSONDecodeError:
        normalized = re.sub(r"\btrue\b", "True", wrapped, flags=re.IGNORECASE)
        normalized = re.sub(r"\bfalse\b", "False", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bnull\b", "None", normalized, flags=re.IGNORECASE)
        try:
            parsed = ast.literal_eval(normalized)
        except (SyntaxError, ValueError):
            parsed = []
            for token in next(
                csv.reader([raw_arguments], skipinitialspace=True)
            ):
                value = token.strip()
                lowered = value.lower()
                if lowered == "true":
                    parsed.append(True)
                elif lowered == "false":
                    parsed.append(False)
                elif lowered in {"null", "none"}:
                    parsed.append(None)
                elif value:
                    parsed.append(value)
                else:
                    raise ValueError(
                        "Tham số Action không được để trống."
                    )

    if not isinstance(parsed, list):
        raise ValueError("Danh sách tham số Action không hợp lệ.")
    return parsed


def _has_explicit_confirmation(user_query: str) -> bool:
    """Nhận diện xác nhận rõ ràng và loại các câu phủ định xác nhận."""
    normalized = " ".join(user_query.lower().split())
    negative_phrases = (
        "chưa xác nhận",
        "không xác nhận",
        "chưa đồng ý",
        "không đồng ý",
        "do not confirm",
        "not confirmed",
    )
    if any(phrase in normalized for phrase in negative_phrases):
        return False

    confirmation_phrases = (
        "tôi xác nhận",
        "tôi đồng ý",
        "xác nhận tạo yêu cầu",
        "đồng ý tạo yêu cầu",
        "i confirm",
    )
    return any(phrase in normalized for phrase in confirmation_phrases)


def _tool_observation(
    tool_name: str,
    arguments: list[Any],
    user_query: str,
    successful_tools: set[str],
) -> str:
    """Kiểm tra guardrails rồi thực thi một tool đã đăng ký."""
    tool = AVAILABLE_TOOLS.get(tool_name)
    if tool is None:
        return json.dumps(
            {
                "ok": False,
                "code": "UNKNOWN_TOOL",
                "message": f"Tool '{tool_name}' không tồn tại.",
                "data": {"available_tools": sorted(AVAILABLE_TOOLS)},
            },
            ensure_ascii=False,
        )

    try:
        inspect.signature(tool).bind(*arguments)
    except TypeError as error:
        return json.dumps(
            {
                "ok": False,
                "code": "INVALID_TOOL_ARGUMENTS",
                "message": str(error),
                "data": None,
            },
            ensure_ascii=False,
        )

    if tool_name == "create_return_request":
        if "check_return_eligibility" not in successful_tools:
            return json.dumps(
                {
                    "ok": False,
                    "code": "ELIGIBILITY_CHECK_REQUIRED",
                    "message": (
                        "Phải kiểm tra và xác nhận đủ điều kiện đổi/trả "
                        "trước khi tạo yêu cầu."
                    ),
                    "data": None,
                },
                ensure_ascii=False,
            )
        if not _has_explicit_confirmation(user_query):
            return json.dumps(
                {
                    "ok": False,
                    "code": "CONFIRMATION_REQUIRED",
                    "message": (
                        "Người dùng chưa xác nhận rõ ràng việc tạo yêu cầu "
                        "đổi/trả."
                    ),
                    "data": None,
                },
                ensure_ascii=False,
            )

    try:
        return str(tool(*arguments))
    except Exception as error:
        return json.dumps(
            {
                "ok": False,
                "code": "TOOL_EXECUTION_ERROR",
                "message": f"Tool gặp lỗi: {error}",
                "data": None,
            },
            ensure_ascii=False,
        )


def _observation_succeeded(observation: str) -> bool:
    try:
        data = json.loads(observation)
        return data.get("ok") is True
    except (json.JSONDecodeError, AttributeError):
        return False


def _safe_final_answer(answer: str) -> str:
    """Không để mã xác minh xuất hiện trong câu trả lời cuối."""
    return VERIFICATION_CODE_PATTERN.sub("[REDACTED]", answer.strip())


def _required_tools_for_query(user_query: str) -> set[str]:
    """Xác định các bằng chứng tool tối thiểu trước khi chấp nhận Final."""
    normalized = " ".join(user_query.lower().split())
    required: set[str] = set()

    asks_order_status = any(
        phrase in normalized
        for phrase in ("kiểm tra trạng thái", "tra cứu trạng thái", "đơn hàng")
    )
    has_verification = bool(
        VERIFICATION_CODE_PATTERN.search(user_query)
    )
    if asks_order_status and has_verification:
        required.add("get_order_status")

    asks_eligibility = any(
        phrase in normalized
        for phrase in (
            "kiểm tra điều kiện",
            "đủ điều kiện",
            "có được đổi",
            "có được trả",
        )
    )
    if asks_eligibility and has_verification:
        required.update({"get_order_status", "check_return_eligibility"})

    asks_creation = any(
        phrase in normalized
        for phrase in ("tạo yêu cầu", "tạo ngay yêu cầu")
    )
    if (
        asks_creation
        and has_verification
        and _has_explicit_confirmation(user_query)
    ):
        required.update(
            {
                "get_order_status",
                "check_return_eligibility",
                "create_return_request",
            }
        )

    return required


def _validate_final_answer(
    answer: str,
    required_tools: set[str],
    successful_tools: set[str],
) -> tuple[bool, str]:
    """Chặn Final thiếu bằng chứng hoặc tuyên bố side effect giả."""
    missing_tools = sorted(required_tools - successful_tools)
    if missing_tools:
        return (
            False,
            "Chưa gọi thành công các tool bắt buộc: "
            + ", ".join(missing_tools),
        )

    normalized = " ".join(answer.lower().split())
    creation_claims = (
        "đã tạo yêu cầu",
        "yêu cầu đã được tạo",
        "được tạo thành công",
    )
    if (
        any(claim in normalized for claim in creation_claims)
        and "create_return_request" not in successful_tools
    ):
        return False, "Không có Observation xác nhận yêu cầu đã được tạo."

    return True, ""


def run_react_agent(user_query: str, provider) -> dict[str, Any]:
    """Chạy vòng lặp ReAct động với tool registry và guardrails."""
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    transcript = [f"User Request: {user_query}"]
    trace: list[dict[str, Any]] = []
    successful_tools: set[str] = set()
    executed_actions: set[str] = set()
    required_tools = _required_tools_for_query(user_query)
    tool_iterations = 0
    llm_calls = 0
    max_llm_calls = MAX_ITERATIONS * 2

    while (
        tool_iterations < MAX_ITERATIONS
        and llm_calls < max_llm_calls
    ):
        llm_calls += 1
        print(
            f"\n--- 🔄 LLM Call {llm_calls}/{max_llm_calls} "
            f"| Tool Step {tool_iterations}/{MAX_ITERATIONS} ---"
        )
        prompt = "\n\n".join(transcript)
        response = provider.generate(prompt, system_prompt=REACT_SYSTEM_PROMPT)
        print(response)

        action_match = ACTION_PATTERN.search(response)
        if action_match:
            # Nếu model tự viết thêm Observation hoặc Final Answer, hệ thống vẫn
            # chỉ lấy Action đầu tiên và bỏ phần kết quả chưa được tool xác nhận.
            tool_iterations += 1
            tool_name = action_match.group(1)
            raw_arguments = action_match.group(2)
            action_key = f"{tool_name}[{raw_arguments}]"

            if action_key in executed_actions:
                observation = json.dumps(
                    {
                        "ok": False,
                        "code": "REPEATED_ACTION_BLOCKED",
                        "message": "Action giống hệt đã được gọi trước đó.",
                        "data": None,
                    },
                    ensure_ascii=False,
                )
            else:
                executed_actions.add(action_key)
                try:
                    arguments = _parse_action_arguments(raw_arguments)
                    observation = _tool_observation(
                        tool_name,
                        arguments,
                        user_query,
                        successful_tools,
                    )
                except ValueError as error:
                    observation = json.dumps(
                        {
                            "ok": False,
                            "code": "INVALID_ACTION_ARGUMENTS",
                            "message": str(error),
                            "data": None,
                        },
                        ensure_ascii=False,
                    )

            if _observation_succeeded(observation):
                successful_tools.add(tool_name)

            print(f"👁️ Observation: {observation}")
            transcript.extend(
                [
                    f"Assistant Action: Action: {action_key}",
                    f"Observation: {observation}",
                ]
            )
            trace.append(
                {
                    "step": tool_iterations,
                    "llm_call": llm_calls,
                    "response": response,
                    "action": action_key,
                    "observation": observation,
                }
            )
            continue

        final_match = FINAL_PATTERN.search(response)
        if final_match:
            candidate_answer = final_match.group(1).strip()
            final_is_valid, rejection_reason = _validate_final_answer(
                candidate_answer,
                required_tools,
                successful_tools,
            )
            if not final_is_valid:
                observation = json.dumps(
                    {
                        "ok": False,
                        "code": "FINAL_ANSWER_REJECTED",
                        "message": rejection_reason,
                        "data": {
                            "successful_tools": sorted(successful_tools),
                            "required_tools": sorted(required_tools),
                        },
                    },
                    ensure_ascii=False,
                )
                print(f"🛡️ Final bị từ chối: {observation}")
                transcript.append(
                    "System Notice: Final Answer trước bị từ chối. "
                    f"{rejection_reason}. Hãy thực hiện Action còn thiếu; "
                    "không được tự tạo Observation."
                )
                trace.append(
                    {
                        "step": tool_iterations,
                        "llm_call": llm_calls,
                        "response": response,
                        "observation": observation,
                    }
                )
                continue

            final_answer = _safe_final_answer(candidate_answer)
            print(f"\n🏁 Final Answer: {final_answer}")
            trace.append(
                {
                    "step": tool_iterations,
                    "llm_call": llm_calls,
                    "response": response,
                    "final_answer": final_answer,
                }
            )
            return {
                "status": "completed",
                "final_answer": final_answer,
                "trace": trace,
            }

        if not action_match:
            observation = json.dumps(
                {
                    "ok": False,
                    "code": "INVALID_REACT_FORMAT",
                    "message": (
                        "Phản hồi phải chứa Action: tool[...] hoặc Final Answer."
                    ),
                    "data": None,
                },
                ensure_ascii=False,
            )
            print(f"👁️ Observation: {observation}")
            transcript.append(
                "System Notice: Phản hồi trước bị từ chối vì model tự tạo "
                "Observation hoặc sai định dạng. Chỉ trả về một Action hoặc "
                "một Final Answer."
            )
            trace.append(
                {
                    "step": tool_iterations,
                    "llm_call": llm_calls,
                    "response": response,
                    "observation": observation,
                }
            )
            continue

    fallback = (
        f"Đã đạt giới hạn {MAX_ITERATIONS} lần gọi tool hoặc giới hạn định dạng "
        "nhưng chưa hoàn tất yêu cầu. "
        "Vui lòng chuyển cho nhân viên hỗ trợ."
    )
    print(f"\n🛡️ GUARDRAIL: {fallback}")
    return {
        "status": "max_iterations",
        "final_answer": fallback,
        "trace": trace,
    }


def _print_test_cases(tests: list[dict[str, Any]]) -> None:
    print("\n📋 TEST CASES")
    for test in tests:
        print(f"  {test['id']}. {test['question']}")


def _read_mode() -> str:
    print("\nChọn chế độ:")
    print("  1. Baseline Chatbot (Mốc 2, không gọi tool)")
    print("  2. ReAct Agent (Mốc 3, có gọi tool)")
    print("  3. So sánh Baseline và ReAct")
    while True:
        choice = input("Lựa chọn [1/2/3]: ").strip()
        if choice in {"1", "2", "3"}:
            return choice
        print("Vui lòng nhập 1, 2 hoặc 3.")


def main() -> None:
    print("=" * 58)
    print("TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI/TRẢ")
    print("=" * 58)

    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(
        f"🔌 Provider: {provider.__class__.__name__} "
        f"(Model: {model_name})"
    )

    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} test cases.")
    try:
        mode = _read_mode()
        print("\nNhập câu hỏi trực tiếp, hoặc dùng:")
        print("  /tests       Xem danh sách test case")
        print("  /test <id>   Chạy một test case, ví dụ: /test 4")
        print("  /mode        Đổi chế độ")
        print("  /quit        Thoát")

        while True:
            raw_query = input("\nBạn: ").strip()
            if not raw_query:
                continue
            if raw_query.lower() in {"/quit", "quit", "exit"}:
                print("👋 Đã kết thúc phiên demo.")
                break
            if raw_query.lower() == "/tests":
                _print_test_cases(tests)
                continue
            if raw_query.lower() == "/mode":
                mode = _read_mode()
                continue
            if raw_query.lower().startswith("/test "):
                try:
                    test_id = int(raw_query.split(maxsplit=1)[1])
                except ValueError:
                    print("ID test phải là một số.")
                    continue
                selected = next(
                    (test for test in tests if test.get("id") == test_id),
                    None,
                )
                if selected is None:
                    print(f"Không tìm thấy test case ID {test_id}.")
                    continue
                user_query = selected["question"]
                print(f"🧪 Test #{test_id}: {user_query}")
            else:
                user_query = raw_query

            if mode in {"1", "3"}:
                print("\n--- CHATBOT BASELINE ---")
                run_baseline_chatbot(user_query, provider)
            if mode in {"2", "3"}:
                print("\n--- REACT AGENT ---")
                run_react_agent(user_query, provider)
    except (EOFError, KeyboardInterrupt):
        print("\n👋 Đã kết thúc phiên demo.")


if __name__ == "__main__":
    main()
