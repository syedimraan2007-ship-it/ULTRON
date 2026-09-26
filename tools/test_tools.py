from system_tools import get_system_info, get_gpu_info


print("ULTRON SYSTEM")
print("=============")

system = get_system_info()

print(f"OS: {system['os']}")
print(f"CPU: {system['cpu']}")
print(
    f"RAM: {system['ram_used_gb']} / "
    f"{system['ram_total_gb']} GB"
)
print(f"RAM usage: {system['ram_percent']}%")

print("\nULTRON GPU")
print("==========")

gpu = get_gpu_info()

print(f"GPU: {gpu['gpu']}")
print(f"VRAM total: {gpu['vram_total_gb']} GB")
print(f"VRAM used: {gpu['vram_used_gb']} GB")
print(f"VRAM free: {gpu['vram_free_gb']} GB")
print(f"GPU usage: {gpu['gpu_utilization_percent']}%")
print(f"VRAM usage: {gpu['memory_utilization_percent']}%")