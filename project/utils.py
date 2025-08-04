import uuid
from functools import lru_cache

def generate_visitor_id():
    """Generates a unique visitor ID."""
    return str(uuid.uuid4())
