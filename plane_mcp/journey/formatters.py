import functools
import logging
import re

logger = logging.getLogger(__name__)

def clean_markdown_escapes(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # Remove backslashes used to escape common markdown characters
    text = re.sub(r'\\([*_\-`#+!\[\]()])', r'\1', text)
    return text

def with_emojification(formatter_func):
    """
    Decorator that applies a specific formatting function to the raw JSON output of a tool.
    If the formatting succeeds, returns a unified string containing the human-readable
    text and a collapsible JSON block.
    If formatting fails (e.g., missing required keys), gracefully falls back to returning the raw JSON.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raw_data = func(*args, **kwargs)
            
            # We only emojify dicts (which represents structured JSON)
            if not isinstance(raw_data, dict):
                return raw_data
                
            if "llmContent" in raw_data and "returnDisplay" in raw_data:
                return raw_data
                
            try:
                # The formatter_func handles the specific logic for this tool's output
                human_text = formatter_func(raw_data)
                
                # If the formatter intentionally returns None or empty, skip emojification
                if not human_text:
                    return raw_data

                return {
                    "llmContent": raw_data,
                    "returnDisplay": human_text
                }

            except Exception as e:
                # Fallthrough to raw JSON on error (the "happy path only" rule)
                logger.debug("Emojification skipped due to error: %s", e)
                return raw_data
                
        return wrapper
    return decorator


def format_help(data: dict) -> str:
    return "Options loaded successfully."


def format_create_ticket(data: dict) -> str:
    if data.get("status") == "error":
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    if data.get("status") == "warning":
        return f"⚠️ Warning: {data.get('message')} (Ticket: {data.get('key', 'UNKNOWN')})"
        
    if "projects" in data:
        return format_help(data)
        
    key = data.get("key", "UNKNOWN")
    title = data.get("name", "[Title]")
    return f"✅ Created {key}: {title}"


def format_update_ticket(data: dict) -> str:
    status = data.get("status", "success")
    msg = data.get("message", "")
    key = data.get("key", "UNKNOWN")
    
    if status == "error":
        return f"❌ Error updating {key}: {msg}"
    elif status == "warning":
        return f"⚠️ Warning for {key}: {msg}"
    return f"✅ Ticket {key} updated successfully."


def get_priority_emoji(priority: str) -> str:
    priority = (priority or "none").lower()
    mapping = {
        "urgent": "🚨",
        "high": "⏫",
        "medium": "🔼",
        "low": "🔽",
        "none": "➖"
    }
    return mapping.get(priority, "➖")

def get_state_emoji(state: str) -> str:
    state = (state or "").lower()
    # Unique colored circles per state
    mapping = {
        "backlog": "⚫",
        "todo": "🟣",
        "in progress": "🔵",
        "started": "🔵",
        "done": "🟢",
        "completed": "🟢",
        "closed": "🟢",
        "cancelled": "🔴",
        "canceled": "🔴",
        "delayed": "🟡"
    }
    return mapping.get(state, "⚪")

def format_search_tickets(data: dict) -> str:
    if data.get("status") == "error":
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    if "projects" in data:
        return format_help(data)
    if "results" not in data:
        return ""
        
    results = data["results"]
    count = len(results)
    if count == 0:
        return "🔍 Found 0 tickets."
        
    lines = []
    for t in results:
        key = t.get("ticket_id") or t.get("key", "UNKNOWN")
        name = t.get("name", "Untitled")
        desc = t.get("description", t.get("description_html", ""))
        
        desc_clean = clean_markdown_escapes(str(desc))
        desc_clean = re.sub(r'<[^>]+>', '', desc_clean)
        desc_clean = " ".join(desc_clean.split())
        
        if len(desc_clean) > 80:
            snippet = desc_clean[:80] + "..."
        else:
            snippet = desc_clean
            
        if snippet:
            lines.append(f"{key} {name}\n{snippet}")
        else:
            lines.append(f"{key} {name}")
            
    return "\n\n".join(lines)


def format_read_ticket(data: dict) -> str:
    if data.get("status") == "error":
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    key = data.get("ticket_id") or data.get("key", "UNKNOWN")
    name = data.get("name", "Unknown Title")
    desc = data.get("description", data.get("description_html", "No description"))
    
    desc_clean = clean_markdown_escapes(str(desc))
    desc_clean = re.sub(r'<[^>]+>', '', desc_clean).strip()
    
    returnDisplay = f"{key} {name}\n\n{desc_clean}"
    if "comments" in data:
        returnDisplay += "\n\nComments:\n" + data["comments"]
        
    return returnDisplay


def format_begin_work(data: dict) -> str:
    status = data.get("status", "success")
    if status == "error":
        return f"❌ Error starting work: {data.get('message', '')}"
        
    ticket_ids = data.get("ticket_ids", [])
    ticket_str = ", ".join(ticket_ids) if ticket_ids else "tickets"
    
    details = data.get("details", {})
    messages = [f"✅ {k}: Processed {ticket_str} - {v}" for k, v in details.items()]
    if not messages:
        return f"✅ Work begun on {ticket_str}."
    return "\n".join(messages)


def format_complete_work(data: dict) -> str:
    status = data.get("status")
    if status == "partial":
        return f"⚠️ {data.get('message', 'Partial completion.')}"
    elif status == "error":
        return f"❌ Error: {data.get('message', '')}"
        
    key = data.get("ticket_id") or data.get("key", "UNKNOWN")
    return f"✅ Ticket {key} transitioned to Done"


def format_transition_ticket(data: dict) -> str:
    if data.get("status") == "error":
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    key = data.get("ticket_id") or data.get("key", "UNKNOWN")
    state = data.get("state", "New State")
    return f"✅ Ticket {key} transitioned to {state}"