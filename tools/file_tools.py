from pathlib import Path
import threading

from core.events import EVENT_BUS, EventType
from core.file_permissions import (
    FILE_CAPABILITIES,
    FileCapability,
)


FILE_SCOPE = Path(r"D:\ultron").resolve()
_FILE_LOCK = threading.RLock()


def _audit(operation: str, path: Path, success: bool) -> None:
    EVENT_BUS.emit(
        EventType.FILE_OPERATION,
        operation=operation,
        path=str(path),
        success=success,
    )


def _scoped_path(path: str) -> Path:
    candidate = Path(path).expanduser()

    if any(part == ".." for part in candidate.parts):
        raise PermissionError("Path traversal is not allowed.")

    if not candidate.is_absolute():
        candidate = FILE_SCOPE / candidate

    resolved = candidate.resolve()

    try:
        resolved.relative_to(FILE_SCOPE)
    except ValueError as exc:
        raise PermissionError(
            "Path is outside the allowed ULTRON scope."
        ) from exc

    return resolved


def _file_operation_path(
    operation: str,
    path: str,
    capability: FileCapability,
) -> Path:
    try:
        FILE_CAPABILITIES.require(capability)
        target = _scoped_path(path)
    except Exception:
        _audit(operation, Path(path), False)
        raise

    return target


def read_file(path: str) -> str:
    target = _file_operation_path(
        "read_file",
        path,
        FileCapability.FILE_READ,
    )

    try:
        with _FILE_LOCK:
            if not target.exists():
                raise FileNotFoundError(f"File does not exist: {target}")

            if not target.is_file():
                raise IsADirectoryError(f"Not a file: {target}")

            content = target.read_text(
                encoding="utf-8",
                errors="replace",
            )

    except Exception:
        _audit("read_file", target, False)
        raise

    _audit("read_file", target, True)
    return content


def write_file(path: str, content: str) -> str:
    target = _file_operation_path(
        "write_file",
        path,
        FileCapability.FILE_WRITE,
    )

    try:
        with _FILE_LOCK:
            if target.exists() and not target.is_file():
                raise IsADirectoryError(f"Not a file: {target}")

            target.write_text(content, encoding="utf-8")

    except Exception:
        _audit("write_file", target, False)
        raise

    _audit("write_file", target, True)
    return f"File written: {target}"


def create_directory(path: str) -> str:
    target = _file_operation_path(
        "create_directory",
        path,
        FileCapability.FILE_WRITE,
    )

    try:
        with _FILE_LOCK:
            target.mkdir(parents=False, exist_ok=False)

    except Exception:
        _audit("create_directory", target, False)
        raise

    _audit("create_directory", target, True)
    return f"Directory created: {target}"


def delete_file(path: str) -> str:
    target = _file_operation_path(
        "delete_file",
        path,
        FileCapability.FILE_DELETE,
    )

    try:
        with _FILE_LOCK:
            if not target.exists():
                raise FileNotFoundError(f"File does not exist: {target}")

            if not target.is_file():
                raise IsADirectoryError(f"Not a file: {target}")

            target.unlink()

    except Exception:
        _audit("delete_file", target, False)
        raise

    _audit("delete_file", target, True)
    return f"File deleted: {target}"

def _safe_path(path: str) -> Path:
    return _scoped_path(path)


def list_files(path: str = "D:\\ultron") -> list[dict]:
    """List files and directories inside a path."""

    target = _file_operation_path(
        "list_files",
        path,
        FileCapability.FILE_READ,
    )

    try:
        with _FILE_LOCK:
            if not target.exists():
                result = [{"error": f"Path does not exist: {target}"}]
                _audit("list_files", target, False)
                return result

            if not target.is_dir():
                result = [{"error": f"Not a directory: {target}"}]
                _audit("list_files", target, False)
                return result

            results = []

            for item in target.iterdir():
                results.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "path": str(item),
                    }
                )

    except OSError:
        _audit("list_files", target, False)
        raise

    _audit("list_files", target, True)
    return results


def search_files(
    query: str,
    path: str = "D:\\ultron",
) -> list[dict]:
    """Search recursively for files whose names contain the query."""

    root = _file_operation_path(
        "search_files",
        path,
        FileCapability.FILE_READ,
    )

    try:
        with _FILE_LOCK:
            if not root.exists():
                result = [{"error": f"Path does not exist: {root}"}]
                _audit("search_files", root, False)
                return result

            if not root.is_dir():
                result = [{"error": f"Not a directory: {root}"}]
                _audit("search_files", root, False)
                return result

            matches = []

            for item in root.rglob("*"):
                if item.is_file() and query.lower() in item.name.lower():
                    matches.append(
                        {
                            "name": item.name,
                            "path": str(item),
                            "extension": item.suffix,
                        }
                    )

    except OSError:
        _audit("search_files", root, False)
        raise

    _audit("search_files", root, True)
    return matches[:100]


def get_file_info(path: str) -> dict:
    """Return information about a file."""

    target = _file_operation_path(
        "get_file_info",
        path,
        FileCapability.FILE_READ,
    )

    try:
        with _FILE_LOCK:
            if not target.exists():
                result = {
                    "error": f"File does not exist: {target}"
                }
                _audit("get_file_info", target, False)
                return result

            if not target.is_file():
                result = {
                    "error": f"Not a file: {target}"
                }
                _audit("get_file_info", target, False)
                return result

            stats = target.stat()

    except OSError:
        _audit("get_file_info", target, False)
        raise

    result = {
        "name": target.name,
        "path": str(target),
        "extension": target.suffix,
        "size_bytes": stats.st_size,
    }
    _audit("get_file_info", target, True)
    return result


def read_text_file(path: str) -> str:
    """Read a UTF-8 text file."""

    target = _file_operation_path(
        "read_text_file",
        path,
        FileCapability.FILE_READ,
    )

    try:
        with _FILE_LOCK:
            if not target.exists():
                result = f"File does not exist: {target}"
                _audit("read_text_file", target, False)
                return result

            if not target.is_file():
                result = f"Not a file: {target}"
                _audit("read_text_file", target, False)
                return result

            result = target.read_text(
                encoding="utf-8",
                errors="replace",
            )

    except OSError as exc:
        _audit("read_text_file", target, False)
        return f"Could not read file: {exc}"

    _audit("read_text_file", target, True)
    return result