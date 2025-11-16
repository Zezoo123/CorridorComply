"""
Utility functions
"""
import uuid


def generate_request_id() -> str:
    """
    Generate a unique request ID (UUID)
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())

