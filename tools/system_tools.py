import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil
from pynvml import (
    nvmlInit,
    nvmlShutdown,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetName,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetUtilizationRates,
)
from core.file_permissions import (
    SYSTEM_CAPABILITIES,
    SystemCapability,
)


ULTRON_ROOT = Path(r"D:\ultron").resolve()
PROTECTED_PROCESS_NAMES = {
    "system",
    "system idle process",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "svchost.exe",
}


def _process_audit(
    operation: str,
    success: bool,
    pid: int | None = None,
    path: str | None = None,
) -> None:
    from core.events import EVENT_BUS, EventType

    EVENT_BUS.emit(
        EventType.PROCESS_OPERATION,
        operation=operation,
        pid=pid,
        path=path,
        success=success,
    )


def _approved_process_roots() -> list[Path]:
    roots = [ULTRON_ROOT]

    for variable in (
        "ProgramFiles",
        "ProgramFiles(x86)",
        "LOCALAPPDATA",
    ):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value).resolve())

    return roots


def _resolve_approved_executable(name_or_path: str) -> Path:
    if not isinstance(name_or_path, str) or not name_or_path.strip():
        raise ValueError("An executable name or path is required.")

    value = name_or_path.strip()

    if any(character in value for character in "\x00\r\n;&|<>`$"):
        raise ValueError("Invalid executable path.")

    candidate = Path(value).expanduser()

    if candidate.is_absolute() or "\\" in value or "/" in value:
        executable = candidate.resolve()
    else:
        executable_name = value
        executable = Path(shutil.which(executable_name) or "")

        if not executable:
            raise FileNotFoundError(
                f"Approved executable was not found: {value}"
            )

        executable = executable.resolve()

    if executable.suffix.casefold() != ".exe":
        raise ValueError("Only executable .exe files may be started.")

    if not executable.is_file():
        raise FileNotFoundError(f"Executable does not exist: {executable}")

    if not any(
        _is_within(executable, root)
        for root in _approved_process_roots()
    ):
        raise PermissionError(
            "Executable is outside the approved application locations."
        )

    return executable


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def start_process(name_or_path: str) -> str:
    """Start one approved executable without shell or command arguments."""

    SYSTEM_CAPABILITIES.require(SystemCapability.PROCESS_START)
    executable = None

    try:
        executable = _resolve_approved_executable(name_or_path)
        process = subprocess.Popen(
            [str(executable)],
            shell=False,
        )
    except (OSError, PermissionError, ValueError) as exc:
        _process_audit(
            "start_process",
            False,
            path=str(executable or name_or_path),
        )
        return f"Could not start process: {exc}"

    _process_audit(
        "start_process",
        True,
        pid=process.pid,
        path=str(executable),
    )
    return f"Process started: {executable} (PID {process.pid})"


def stop_process(pid: int) -> str:
    """Request a graceful stop for one non-protected process."""

    SYSTEM_CAPABILITIES.require(SystemCapability.PROCESS_STOP)

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        _process_audit("stop_process", False, pid=pid if isinstance(pid, int) else None)
        return "Invalid process ID."

    process = None

    try:
        process = psutil.Process(pid)
        name = (process.name() or "").casefold()

        if pid == os.getpid() or pid <= 4 or name in PROTECTED_PROCESS_NAMES:
            _process_audit(
                "stop_process",
                False,
                pid=pid,
            )
            return "Refusing to stop a protected process."

        executable = None
        try:
            executable = process.exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            pass

        process.terminate()

        try:
            process.wait(timeout=2)
        except psutil.TimeoutExpired:
            _process_audit(
                "stop_process",
                False,
                pid=pid,
                path=executable,
            )
            return "Process did not stop before the timeout."

    except psutil.NoSuchProcess:
        _process_audit("stop_process", False, pid=pid)
        return "Process no longer exists."
    except psutil.AccessDenied:
        _process_audit("stop_process", False, pid=pid)
        return "Access denied while stopping the process."
    except OSError as exc:
        _process_audit("stop_process", False, pid=pid)
        return f"Could not stop process: {exc}"

    _process_audit(
        "stop_process",
        True,
        pid=pid,
        path=executable,
    )
    return f"Process stopped: PID {pid}"


def get_system_info() -> dict:
    """Return read-only system information."""

    SYSTEM_CAPABILITIES.require(SystemCapability.SYSTEM_INFO)

    memory = psutil.virtual_memory()
    disk = None

    try:
        disk = psutil.disk_usage("D:\\")
    except OSError:
        pass

    gpu_name = None

    try:
        gpu_name = get_gpu_info().get("gpu")
    except Exception:
        pass

    cpu_model = platform.processor() or platform.machine()
    cpu_usage = psutil.cpu_percent(interval=0.1)
    uptime_seconds = max(0, int(time.time() - psutil.boot_time()))

    return {
        "os": platform.platform(),
        "os_version": platform.version(),
        "hostname": platform.node(),
        "cpu": cpu_model,
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
        "ram_used_gb": round(memory.used / (1024 ** 3), 2),
        "ram_available_gb": round(memory.available / (1024 ** 3), 2),
        "ram_percent": memory.percent,
        "cpu_usage_percent": cpu_usage,
        "disk": {
            "drive": "D:",
            "available": disk is not None,
            "total_gb": round(disk.total / (1024 ** 3), 2) if disk else None,
            "used_gb": round(disk.used / (1024 ** 3), 2) if disk else None,
            "free_gb": round(disk.free / (1024 ** 3), 2) if disk else None,
        },
        "python_version": sys.version.split()[0],
        "uptime_seconds": uptime_seconds,
        "gpu": {
            "available": gpu_name is not None,
            "name": gpu_name,
        },
    }


def get_processes() -> list[dict]:
    """Return safe, read-only metadata for running processes."""

    SYSTEM_CAPABILITIES.require(SystemCapability.PROCESS_INFO)

    processes = []

    for process in psutil.process_iter(["pid", "name"]):
        try:
            process_info = process.info
            process_data = {
                "pid": process_info["pid"],
                "name": process_info.get("name") or "Unknown",
                "cpu_percent": None,
                "memory_mb": None,
                "exe": None,
            }

            try:
                process_data["cpu_percent"] = process.cpu_percent(
                    interval=None
                )
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            try:
                process_data["memory_mb"] = round(
                    process.memory_info().rss / (1024 ** 2),
                    2,
                )
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            try:
                process_data["exe"] = process.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                pass

            processes.append(process_data)

        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue

    return processes


def get_gpu_info() -> dict:
    """Return NVIDIA GPU information."""

    nvmlInit()

    try:
        handle = nvmlDeviceGetHandleByIndex(0)

        name = nvmlDeviceGetName(handle)

        if isinstance(name, bytes):
            name = name.decode("utf-8")

        memory = nvmlDeviceGetMemoryInfo(handle)
        utilization = nvmlDeviceGetUtilizationRates(handle)

        return {
            "gpu": name,
            "vram_total_gb": round(memory.total / (1024 ** 3), 2),
            "vram_used_gb": round(memory.used / (1024 ** 3), 2),
            "vram_free_gb": round(memory.free / (1024 ** 3), 2),
            "gpu_utilization_percent": utilization.gpu,
            "memory_utilization_percent": utilization.memory,
        }

    finally:
        nvmlShutdown()


def get_battery_info() -> dict:
    """Return laptop battery information."""

    battery = psutil.sensors_battery()

    if battery is None:
        return {
            "available": False,
        }

    return {
        "available": True,
        "percent": battery.percent,
        "plugged_in": battery.power_plugged,
        "seconds_remaining": battery.secsleft,
    }


def get_temperature_info() -> dict:
    """Return available system temperature sensors."""

    try:
        temperatures = psutil.sensors_temperatures()
    except AttributeError:
        return {
            "available": False,
            "reason": "Temperature sensors are not exposed by this Windows configuration.",
        }

    if not temperatures:
        return {
            "available": False,
            "reason": "No temperature sensors were exposed to Python.",
        }

    result = {}

    for name, entries in temperatures.items():
        result[name] = []

        for entry in entries:
            result[name].append(
                {
                    "label": entry.label,
                    "current_c": entry.current,
                    "high_c": entry.high,
                    "critical_c": entry.critical,
                }
            )

    return {
        "available": True,
        "sensors": result,
    }


def get_system_status() -> str:
    """Return a concise read-only summary of current system status."""

    status_parts = []

    try:
        system_info = get_system_info()
        status_parts.append(
            f"CPU {system_info['cpu_usage_percent']}%"
        )
        status_parts.append(
            "RAM "
            f"{system_info['ram_used_gb']}/{system_info['ram_total_gb']} GB "
            f"({system_info['ram_percent']}%)"
        )
    except Exception:
        status_parts.append("CPU/RAM unavailable")

    try:
        gpu_info = get_gpu_info()
        status_parts.append(
            f"GPU {gpu_info['gpu']} "
            f"({gpu_info['gpu_utilization_percent']}% utilization)"
        )
    except Exception:
        status_parts.append("GPU unavailable")

    try:
        battery_info = get_battery_info()
        if battery_info.get("available"):
            power_state = (
                "plugged in"
                if battery_info["plugged_in"]
                else "on battery"
            )
            status_parts.append(
                f"Battery {battery_info['percent']}% ({power_state})"
            )
    except Exception:
        status_parts.append("Battery unavailable")

    try:
        temperature_info = get_temperature_info()
        if temperature_info.get("available"):
            temperatures = []

            for sensor_name, entries in temperature_info["sensors"].items():
                for entry in entries:
                    current_c = entry.get("current_c")
                    if current_c is not None:
                        label = entry.get("label") or sensor_name
                        temperatures.append(f"{label} {current_c} C")

            if temperatures:
                status_parts.append("Temperature " + ", ".join(temperatures[:3]))
    except Exception:
        status_parts.append("Temperature unavailable")

    if not status_parts:
        return "System status unavailable."

    return "System status: " + "; ".join(status_parts) + "."