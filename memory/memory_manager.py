from difflib import SequenceMatcher
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = (
    Path(__file__).resolve().parent
    / "ultron_memory.db"
)


def initialize_database() -> None:
    """Create the memory database and table."""

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.commit()


def _normalize_memory_content(content: str) -> str:
    normalized = "".join(
        character if character.isalnum() else " "
        for character in content.casefold()
    )

    return " ".join(normalized.split())


def _memory_already_exists(connection: sqlite3.Connection, content: str) -> bool:
    normalized_content = _normalize_memory_content(content)
    rows = connection.execute(
        "SELECT content FROM memories"
    ).fetchall()

    for (existing_content,) in rows:
        normalized_existing = _normalize_memory_content(existing_content)

        if normalized_existing == normalized_content:
            return True

        if SequenceMatcher(
            None,
            normalized_existing,
            normalized_content,
        ).ratio() >= 0.95:
            return True

    return False


def save_memory(content: str) -> str:
    """Save a memory."""

    content = content.strip()

    if not content:
        return "Memory was empty."

    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    with sqlite3.connect(DB_PATH) as connection:
        if _memory_already_exists(connection, content):
            return "Memory already exists."

        connection.execute(
            """
            INSERT INTO memories (content, created_at)
            VALUES (?, ?)
            """,
            (content, timestamp),
        )

        connection.commit()

    return "Memory saved."


def search_memories(
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Search stored memories."""

    query = query.strip()

    if not query:
        return []

    normalized_query = _normalize_memory_content(query)
    query_words = normalized_query.split()
    result_limit = min(max(limit, 0), 10)

    if not query_words or not result_limit:
        return []

    with sqlite3.connect(DB_PATH) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT id, content, created_at
            FROM memories
            """
        ).fetchall()

    scored_rows = []

    for row in rows:
        normalized_content = _normalize_memory_content(row["content"])
        content_words = normalized_content.split()
        exact_phrase = normalized_query in normalized_content
        exact_word_matches = sum(
            query_word in content_words
            for query_word in query_words
        )
        partial_word_matches = sum(
            any(
                query_word in content_word
                or content_word in query_word
                for content_word in content_words
                if len(content_word) >= 3
            )
            for query_word in query_words
            if len(query_word) >= 3
            if query_word not in content_words
        )

        if exact_phrase:
            relevance = (3, exact_word_matches, len(query_words))
        elif exact_word_matches == len(query_words):
            relevance = (2, exact_word_matches, partial_word_matches)
        elif exact_word_matches or partial_word_matches:
            relevance = (1, exact_word_matches, partial_word_matches)
        else:
            continue

        scored_rows.append((relevance, row["id"], row))

    scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for _, _, row in scored_rows[:result_limit]
    ]


def get_recent_memories(
    limit: int = 10,
) -> list[dict]:
    """Return the most recent memories."""

    with sqlite3.connect(DB_PATH) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT id, content, created_at
            FROM memories
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]