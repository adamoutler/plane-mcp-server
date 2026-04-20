import json
import logging
from typing import Any, Callable, TypeVar, cast
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Callable[..., Any])

def _clean_and_convert(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            val = _clean_and_convert(v)
            # Remove None, empty lists, empty dicts, empty strings
            # But preserve 0, False, etc.
            if val not in (None, "", [], {}):
                cleaned[k] = val
        return cleaned
    elif isinstance(obj, list):
        cleaned_list = [_clean_and_convert(v) for v in obj]
        # Remove empty items from list if desired, but here we just convert
        return [v for v in cleaned_list if v not in (None, "", [], {})]
    return obj


def format_as_json(raw_data: Any) -> Any:
    """Convert a dict or list to minified JSON string.

    Args:
        raw_data: Tool output (typically dict or list).

    Returns:
        JSON string if input is dict/list, original value otherwise.
        On formatting failure, returns original data unchanged.
    """
    if not isinstance(raw_data, (dict, list)):
        return raw_data

    try:
        cleaned_data = _clean_and_convert(raw_data)
        json_str = json.dumps(
            cleaned_data,
            separators=(',', ':')
        )
        return json_str.strip()
    except Exception as e:
        logger.debug("JSON formatting failed: %s", e)
        return raw_data


def with_json(func: T) -> T:
    """Decorator that converts a tool's dict/list return value to minified JSON.

    Must be applied OUTSIDE (above) mcp_error_boundary so that error
    dicts also get JSON-formatted. Stack order:

        @mcp.tool()
        @with_json
        @mcp_error_boundary
        def my_tool(...) -> dict: ...
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        return format_as_json(result)

    if 'return' in wrapper.__annotations__:
        wrapper.__annotations__['return'] = Any

    return cast(T, wrapper)
