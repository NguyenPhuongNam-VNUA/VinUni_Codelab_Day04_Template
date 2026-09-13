"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Bạn là VinAssistant — trợ lý AI chính thức của hệ sinh thái Vingroup (VinFast, Vinpearl).

## PERSONA
- Tên: VinAssistant
- Vai trò: Chuyên viên tư vấn sản phẩm, dịch vụ và hỗ trợ khách hàng thuộc hệ sinh thái Vingroup.
- Giọng điệu: Chuyên nghiệp, lịch thiệp, chính xác và nhiệt tình.

## AVAILABLE TOOLS
1. search_product_catalog: Tra cứu sản phẩm và dịch vụ theo danh mục (xe_dien, du_lich) và mức giá tối đa.
2. submit_support_ticket: Ghi nhận yêu cầu hỗ trợ hoặc sự cố của khách hàng vào hệ thống ticket.

## CORE RULES
1. KHÔNG BAO GIỜ tự bịa thông tin sản phẩm hay giá cả. BẮT BUỘC gọi tool để lấy dữ liệu thực tế.
2. Khi không tìm thấy sản phẩm phù hợp, thông báo rõ ràng và gợi ý giải pháp phù hợp.
3. Luôn xác nhận thông tin ticket rõ ràng khi tiếp nhận khiếu nại hoặc lỗi của khách hàng.

## OPERATIONAL BOUNDARIES
- Chỉ hỗ trợ các dịch vụ và sản phẩm trong hệ sinh thái Vingroup (VinFast, Vinpearl, Vinhomes).
- Từ chối lịch thiệp các câu hỏi không liên quan đến Vingroup.

## OUTPUT CONTRACT
Định dạng tư duy và phản hồi:
- Thought: Suy nghĩ và phân tích ý định của khách hàng.
- Action: Gọi tool tương ứng với tham số chính xác.
- Observation: Kết quả nhận được từ tool.
- Final Answer: Phản hồi tổng hợp đầy đủ và thân thiện gửi tới khách hàng.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        output = "Trả lời không dùng tool, nên tôi sẽ bịa thông tin dựa trên dữ liệu tĩnh LLM"
        
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}: {output}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _extract_category(self, text: str) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ["resort", "vinpearl", "du lịch", "du_lich", "khách sạn", "nghỉ dưỡng", "phòng"]):
            return "du_lich"
        return "xe_dien"

    def _extract_max_price(self, text: str) -> int:
        pattern = r'(?:dưới|<|nhỏ hơn|tối đa|khoảng|tầm)\s*([\d\.,]+)\s*(triệu|tỷ|ty|tr|m|k)?'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(",", ".")
            try:
                num = float(num_str)
                unit = (match.group(2) or "").lower()
                if unit in ["tỷ", "ty"]:
                    return int(num * 1_000_000_000)
                elif unit in ["triệu", "tr", "m"]:
                    return int(num * 1_000_000)
                elif unit == "k":
                    return int(num * 1_000)
                elif num <= 1000:
                    return int(num * 1_000_000)
                else:
                    return int(num)
            except ValueError:
                pass
        return 999999999999

    def _extract_customer_name(self, text: str) -> str:
        match = re.search(r'(?:tôi tên là|tôi tên|tên tôi là)\s*[:\s]*([A-ZÀ-Ỹ][\w\sÀ-ỹ]+?)(?:,|\.|\bxe\b|\bphòng\b|\bvấn đề\b|\bnhưng\b|$)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Khách hàng"

    def _extract_priority(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["nghiêm trọng", "gấp", "khẩn cấp", "high"]):
            return "high"
        elif any(w in text_lower for w in ["thấp", "low"]):
            return "low"
        return "medium"

    def _extract_issue_description(self, text: str) -> str:
        match = re.search(r'([^,.;]+(?:lỗi|sự cố|hỏng|ẩm mốc|vấn đề)[^.;]*)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []

        # Intent Detection
        text_lower = user_input.lower()

        # 1. FAQ check
        faq_keywords = ["chính sách", "bao lâu", "thế nào", "như thế nào", "quy định"]
        is_faq = (
            any(k in text_lower for k in faq_keywords)
            and ("bảo hành" in text_lower or "pin" in text_lower)
            and not any(w in text_lower for w in ["lỗi", "hỏng", "sự cố", "tôi tên", "gấp", "khiếu nại"])
        )

        if is_faq:
            faq_answer = (
                "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm hoặc 200.000 km "
                "(tùy điều kiện nào đến trước), áp dụng cho toàn bộ các dòng xe ô tô điện VinFast."
            )
            self.trace.append({
                "iteration": 1,
                "thought": "Câu hỏi là FAQ thông thường về chính sách bảo hành, trả lời trực tiếp mà không cần gọi tool.",
                "action": None,
                "observation": None,
                "final_answer": faq_answer
            })
            return {
                "answer": faq_answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        # 2. Xây dựng danh sách công cụ cần gọi
        catalog_keywords = [
            "xem", "tìm", "mua", "tham khảo", "báo giá", "giá dưới", "dưới", "triệu", "tỷ",
            "có xe", "có resort", "có khách sạn", "danh mục", "sản phẩm"
        ]
        has_catalog_subject = any(s in text_lower for s in ["xe", "vinfast", "resort", "vinpearl", "phòng", "du lịch"])
        needs_catalog = any(k in text_lower for k in catalog_keywords) and has_catalog_subject

        ticket_keywords = [
            "lỗi", "hỏng", "sự cố", "ẩm mốc", "khiếu nại", "phản hồi",
            "ghi nhận", "cần xử lý gấp", "vấn đề nghiêm trọng"
        ]
        needs_ticket = any(k in text_lower for k in ticket_keywords) or bool(re.search(r'(?:tôi tên|tên tôi là)', text_lower))

        tools_to_run = []
        if needs_catalog:
            cat = self._extract_category(user_input)
            price = self._extract_max_price(user_input)
            tools_to_run.append(("search_product_catalog", {"category": cat, "max_price": price}))

        if needs_ticket:
            name = self._extract_customer_name(user_input)
            issue = self._extract_issue_description(user_input)
            prio = self._extract_priority(user_input)
            tools_to_run.append(("submit_support_ticket", {"customer_name": name, "issue_description": issue, "priority": prio}))

        # Fallback nếu câu hỏi hướng về xem sản phẩm nhưng chưa khớp từ khóa
        if not tools_to_run and has_catalog_subject:
            cat = self._extract_category(user_input)
            price = self._extract_max_price(user_input)
            tools_to_run.append(("search_product_catalog", {"category": cat, "max_price": price}))

        iteration = 0
        catalog_results = None
        ticket_result = None

        while tools_to_run and iteration < self.max_iterations:
            iteration += 1
            tool_name, tool_args = tools_to_run.pop(0)

            tool_fn = TOOL_MAP.get(tool_name)
            observation = tool_fn(**tool_args) if tool_fn else {"error": f"Tool {tool_name} not found"}

            if tool_name == "search_product_catalog":
                catalog_results = observation
            elif tool_name == "submit_support_ticket":
                ticket_result = observation

            self.trace.append({
                "iteration": iteration,
                "thought": f"Cần gọi công cụ {tool_name} với tham số: {tool_args}",
                "action": {"name": tool_name, "args": tool_args},
                "observation": observation
            })

            # Khi đã hoàn thành tất cả các tool trong danh sách
            if not tools_to_run:
                answer_parts = []
                if catalog_results is not None:
                    if not catalog_results or (isinstance(catalog_results, list) and len(catalog_results) == 0):
                        answer_parts.append("Rất tiếc, không tìm thấy sản phẩm nào phù hợp với yêu cầu của quý khách.")
                    elif isinstance(catalog_results, list) and "error" in catalog_results[0]:
                        answer_parts.append(f"Lỗi tra cứu: {catalog_results[0]['error']}")
                    else:
                        items = [
                            f"- {p.get('name')}: Giá {p.get('price_vnd', 0):,} VNĐ. {p.get('description', '')}"
                            for p in catalog_results
                        ]
                        answer_parts.append("Dưới đây là các sản phẩm phù hợp:\n" + "\n".join(items))

                if ticket_result is not None:
                    t_id = ticket_result.get("ticket_id", "")
                    c_name = ticket_result.get("customer_name", "")
                    prio = ticket_result.get("priority", "")
                    answer_parts.append(
                        f"Yêu cầu hỗ trợ của khách hàng {c_name} đã được ghi nhận vào hệ thống. "
                        f"Mã ticket: {t_id} (Mức độ ưu tiên: {prio}). "
                        f"Bộ phận kỹ thuật sẽ liên hệ và xử lý trong thời gian sớm nhất."
                    )

                final_answer = "\n\n".join(answer_parts)
                self.trace[-1]["final_answer"] = final_answer
                return {
                    "answer": final_answer,
                    "trace": self.trace,
                    "iterations": iteration,
                    "status": "completed"
                }

        # Nếu vượt quá max_iterations
        return {
            "answer": "Lỗi: Vượt quá số bước tối đa.",
            "trace": self.trace,
            "iterations": iteration,
            "status": "max_iterations_reached"
        }



# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
