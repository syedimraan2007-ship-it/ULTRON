from memory.memory_manager import (
    save_memory,
    search_memories,
    get_recent_memories,
)


def remember(content: str) -> str:
    """Save a useful fact to long-term memory."""
    return save_memory(content)


def recall(query: str) -> list[dict]:
    """Search long-term memory."""
    return search_memories(query)


def recent_memories(limit: int = 10) -> list[dict]:
    """Get recent memories."""
    return get_recent_memories(limit)