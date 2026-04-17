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
            import json
            raw_data = func(*args, **kwargs)
            
            # We only emojify dicts (which represents structured JSON)
            if not isinstance(raw_data, dict):
                return str(raw_data)
                
            if "llmContent" in raw_data and "returnDisplay" in raw_data:
                return json.dumps(raw_data, indent=2)
                
            try:
                # The formatter_func handles the specific logic for this tool's output
                human_text = formatter_func(raw_data)
                
                # If the formatter intentionally returns None or empty, skip emojification
                if not human_text:
                    return json.dumps(raw_data, indent=2)

                return human_text

            except Exception as e:
                # Fallthrough to raw JSON on error (the "happy path only" rule)
                logger.debug("Emojification skipped due to error: %s", e)
                return json.dumps(raw_data, indent=2)
                
        return wrapper
    return decorator


def format_help(data: dict) -> str:
    projects = data.get("projects", [])
    priorities = data.get("priorities", [])
    
    lines = []
    for p in projects:
        slug = p.get("project_slug", "UNKNOWN")
        name = p.get("name", "")
        states = ",".join(p.get("states", []))
        labels = ",".join(p.get("labels", []))
        
        line = f"📁{slug}({name}) 🔄{states}"
        if labels:
            line += f" 🏷️{labels}"
        lines.append(line)
        
    if priorities:
        lines.append(f"⚡{','.join(priorities)}")
        
    lines.append("\nField Definitions:\nPriority: 🚨urgent ⏫high 🔼medium 🔽low ➖none\nStatus: ⚫Backlog 🟣Todo 🔵In Progress 🟢Done 🔴Cancelled 🟡delayed")
    return "\n".join(lines)


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


def get_priority_emoji(priority: str | dict) -> str:
    if isinstance(priority, dict):
        priority = priority.get("name", "")
    priority = str(priority or "").lower()
    mapping = {
        "urgent": "🚨",
        "high": "⏫",
        "medium": "🔼",
        "low": "🔽",
        "none": "➖"
    }
    return mapping.get(priority, "➖")

def get_state_emoji(state: str | dict) -> str:
    if isinstance(state, dict):
        state = state.get("name", "")
    state = str(state or "").lower()
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
        state = t.get("state", "None")
        priority = t.get("priority", "none")
        
        state_emoji = get_state_emoji(state)
        priority_emoji = get_priority_emoji(priority)
            
        lines.append(f"{state_emoji}{priority_emoji}{key} {name}")
        
    if data.get("next_cursor"):
        lines.append(f"⏭️{data['next_cursor']}")
    if data.get("prev_cursor"):
        lines.append(f"⏮️{data['prev_cursor']}")
            
    return "\n".join(lines)


def format_read_ticket(data: dict) -> str:
    if "error" in data or "message" in data:
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    key = data.get("ticket_id") or data.get("key", "UNKNOWN")
    name = data.get("name", "Unknown Title")
    state = data.get("state", "None")
    priority = data.get("priority", "none")
    desc = data.get("description", "")
    
    state_emoji = get_state_emoji(state)
    priority_emoji = get_priority_emoji(priority)
    
    returnDisplay = f"{state_emoji}{priority_emoji}{key} {name}"
    
    if desc:
        import re
        desc_clean = re.sub(r'<[^>]+>', '', str(desc)).strip()
        if desc_clean:
            returnDisplay += f"\n📝 {desc_clean}"
            
    labels = data.get("labels", [])
    if labels:
        if isinstance(labels, list) and len(labels) > 0 and isinstance(labels[0], dict):
            labels = [lbl.get("name", "") for lbl in labels]
        returnDisplay += f"\n🏷️ {','.join(labels)}"
        
    assignees = data.get("assignees", [])
    if assignees:
        if isinstance(assignees, list) and len(assignees) > 0 and isinstance(assignees[0], dict):
            assignees = [a.get("display_name", a.get("username", "")) for a in assignees]
        returnDisplay += f"\n👤 {','.join([str(a) for a in assignees])}"
    
    if "comments" in data:
        returnDisplay += "\n💬 Comments:\n" + data["comments"]
        
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
    name = data.get("name", "")
    state = data.get("state", "Done")
    priority = data.get("priority", "none")
    
    state_emoji = get_state_emoji(state)
    priority_emoji = get_priority_emoji(priority)
    
    return f"✅{state_emoji}{priority_emoji}{key} {name}".strip()


def format_transition_ticket(data: dict) -> str:
    if data.get("status") == "error":
        return f"❌ Error: {data.get('message', 'Unknown error')}"
    key = data.get("ticket_id") or data.get("key", "UNKNOWN")
    state = data.get("state", "New State")
    return f"✅ Ticket {key} transitioned to {state}"