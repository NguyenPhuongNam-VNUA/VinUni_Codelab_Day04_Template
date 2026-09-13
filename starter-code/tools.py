import json
import os
from typing import List, Dict, Any
from datetime import datetime

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")

# ---------------------------------------------------------------------------
# Tool #1: search_product_catalog
# TODO: Hoàn thiện hàm này — đọc file product_catalog.json, lọc theo category và max_price.
# ---------------------------------------------------------------------------

def search_product_catalog(category: str, max_price: int = 999999999999) -> List[Dict[str, Any]]:
    """
    Tra cứu sản phẩm/dịch vụ Vingroup theo danh mục và giá tối đa.
    
    Args:
        category: Loại sản phẩm ('xe_dien' hoặc 'du_lich').
        max_price: Giá tối đa (VNĐ). Mặc định không giới hạn.
    
    Returns:
        Danh sách sản phẩm phù hợp điều kiện.
    """
    catalog_file = os.path.join(RAW_DATA_DIR, "product_catalog.json")
    if not os.path.exists(catalog_file):
        return [{"error": "Product catalog file not found."}]

    with open(catalog_file, "r", encoding="utf-8") as f:
        products = json.load(f)

    # Lọc sản phẩm theo category và max_price
    results = [
        p for p in products
        if p.get("category", "").lower() == category.lower()
        and p.get("price_vnd", float("inf")) <= max_price
    ]
    return results



# ---------------------------------------------------------------------------
# Tool #2: submit_support_ticket
# TODO: Hoàn thiện hàm này — tạo ticket mới và lưu vào support_tickets.json.
# ---------------------------------------------------------------------------

def submit_support_ticket(
    customer_name: str,
    issue_description: str,
    priority: str = "medium"
) -> Dict[str, Any]:
    """
    Ghi nhận yêu cầu hỗ trợ của khách hàng vào hệ thống ticket.
    
    Args:
        customer_name: Tên khách hàng.
        issue_description: Mô tả vấn đề cần hỗ trợ.
        priority: Mức độ ưu tiên ('low', 'medium', 'high'). Mặc định 'medium'.
    
    Returns:
        Thông tin ticket vừa tạo bao gồm ticket_id, status.
    """
    tickets_file = os.path.join(RAW_DATA_DIR, "support_tickets.json")

    # Load existing tickets
    existing_tickets = []
    if os.path.exists(tickets_file):
        with open(tickets_file, "r", encoding="utf-8") as f:
            try:
                existing_tickets = json.load(f)
            except json.JSONDecodeError:
                existing_tickets = []

    # Generate ticket ID
    today = datetime.now().strftime("%Y%m%d")
    seq = len(existing_tickets) + 1
    ticket_id = f"TK-{today}-{seq:03d}"

    # Create & save new ticket
    new_ticket = {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority.lower(),
        "status": "open",
        "created_at": datetime.now().isoformat() + "+07:00",
        "category": "general"
    }
    existing_tickets.append(new_ticket)

    with open(tickets_file, "w", encoding="utf-8") as f:
        json.dump(existing_tickets, f, indent=2, ensure_ascii=False)

    return {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "priority": priority.lower(),
        "status": "open",
        "message": f"Ticket {ticket_id} đã được tạo thành công."
    }


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS — JSON Schemas mô tả cho LLM
# TODO: Định nghĩa JSON Schema cho từng tool (name, description, parameters).
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
    "name": "search_product_catalog",
    "description": "Search products in catalog by category and max price.",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["xe_dien", "du_lich", "bat_dong_san"],
                "description": "Category to search in"
            },
            "max_price": {
                "type": "integer",
                "minimum": 0,
                "description": "Maximum price (VND)"
            }
        },
        "required": ["category"]
    }
},
    {
    "name": "submit_support_ticket",
    "description": "Create a support ticket for customer issues.",
    "parameters": {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Customer's full name"
            },
            "issue_description": {
                "type": "string",
                "description": "Description of the issue"
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "default": "medium",
                "description": "Ticket priority"
            }
        },
        "required": ["customer_name", "issue_description"]
    }
}
]


# ---------------------------------------------------------------------------
# TOOL_MAP — Ánh xạ tên tool → hàm thực thi
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "search_product_catalog": search_product_catalog,
    "submit_support_ticket": submit_support_ticket
}
