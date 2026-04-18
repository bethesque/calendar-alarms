import re
from datetime import datetime, date
import dataclasses

def sanitise_filename(text):
    """Convert text to a safe filename by removing/replacing unsafe characters."""
    # Remove or replace unsafe characters
    safe_text = re.sub(r'[<>:"/\\|?*]', '', text)  # Remove filesystem-unsafe chars
    safe_text = re.sub(r'[^\w\s-]', '', safe_text)  # Remove other special chars except spaces, hyphens, underscores
    safe_text = re.sub(r'\s+', '_', safe_text)  # Replace spaces with underscores
    safe_text = safe_text.strip('_-')  # Remove leading/trailing underscores/hyphens
    safe_text = safe_text.lower()  # Convert to lowercase for consistency

    # Limit length to avoid filesystem issues
    if len(safe_text) > 200:
        safe_text = safe_text[:200].rstrip('_-')

    return safe_text

def strip_ansi(text):
    # Regex to match ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def json_default_encoder(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    return str(o)