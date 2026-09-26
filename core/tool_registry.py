from memory.memory_manager import (
    initialize_database,
    save_memory,
    search_memories,
    get_recent_memories,
)

from tools.system_control import (
    lock_computer,
    mute_audio,
    open_task_manager,
    open_settings,
)

from memory.memory_tools import (
    remember,
    recall,
    recent_memories,
)

from tools.system_tools import (
    get_system_info,
    get_gpu_info,
    get_processes,
    start_process,
    stop_process,
    get_battery_info,
    get_temperature_info,
    get_system_status,
)

from tools.datetime_tools import get_datetime

from tools.app_tools import (
    launch_application,
    open_application,
    open_url,
)

from tools.desktop_tools import (
    analyze_screen,
    focus_window,
    find_window,
    get_windows,
    get_screen_text,
    keyboard_press,
    keyboard_type,
    mouse_click,
    mouse_move,
    screenshot,
    vision_analyze,
)

from tools.web_tools import (
    open_search_results,
    web_fetch,
    web_search,
)

from tools.file_tools import (
    create_directory,
    delete_file,
    list_files,
    read_file,
    search_files,
    get_file_info,
    read_text_file,
    write_file,
)




AVAILABLE_FUNCTIONS = {
    "open_url": open_url,
    "open_search_results": open_search_results,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "get_system_info": get_system_info,
    "get_gpu_info": get_gpu_info,
    "get_processes": get_processes,
    "start_process": start_process,
    "stop_process": stop_process,
    "get_battery_info": get_battery_info,
    "get_temperature_info": get_temperature_info,
    "get_system_status": get_system_status,
    "get_datetime": get_datetime,
    "open_application": open_application,
    "launch_application": launch_application,
    "remember": remember,
    "recall": recall,
    "recent_memories": recent_memories,
    "list_files": list_files,
    "search_files": search_files,
    "get_file_info": get_file_info,
    "read_text_file": read_text_file,
    "read_file": read_file,
    "write_file": write_file,
    "create_directory": create_directory,
    "delete_file": delete_file,
    "screenshot": screenshot,
    "vision_analyze": vision_analyze,
    "analyze_screen": analyze_screen,
    "find_window": find_window,
    "get_screen_text": get_screen_text,
    "mouse_move": mouse_move,
    "mouse_click": mouse_click,
    "keyboard_type": keyboard_type,
    "keyboard_press": keyboard_press,
    "get_windows": get_windows,
    "focus_window": focus_window,
    "lock_computer": lock_computer,
    "mute_audio": mute_audio,
    "open_task_manager": open_task_manager,
    "open_settings": open_settings,
}


TOOLS = [
    open_url,
    open_search_results,
    web_search,
    web_fetch,
    lock_computer,
mute_audio,
open_task_manager,
open_settings,
    get_system_info,
    get_gpu_info,
    get_processes,
    start_process,
    stop_process,
    get_battery_info,
    get_temperature_info,
    get_system_status,
    get_datetime,
    open_application,
    launch_application,
    remember,
    recall,
    recent_memories,
    list_files,
    search_files,
    get_file_info,
    read_text_file,
    read_file,
    write_file,
    create_directory,
    delete_file,
    screenshot,
    vision_analyze,
    analyze_screen,
    find_window,
    get_screen_text,
    mouse_move,
    mouse_click,
    keyboard_type,
    keyboard_press,
    get_windows,
    focus_window,
]

def get_tool(name: str):
    return AVAILABLE_FUNCTIONS.get(name)