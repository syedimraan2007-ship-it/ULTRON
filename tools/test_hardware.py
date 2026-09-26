from system_tools import (
    get_system_info,
    get_gpu_info,
    get_battery_info,
    get_temperature_info,
)


print("=" * 60)
print("ULTRON HARDWARE TEST")
print("=" * 60)


print("\nSYSTEM")
print("------")

system = get_system_info()

for key, value in system.items():
    print(f"{key}: {value}")


print("\nGPU")
print("---")

gpu = get_gpu_info()

for key, value in gpu.items():
    print(f"{key}: {value}")


print("\nBATTERY")
print("-------")

battery = get_battery_info()

for key, value in battery.items():
    print(f"{key}: {value}")


print("\nTEMPERATURE")
print("-----------")

temperature = get_temperature_info()

print(temperature)