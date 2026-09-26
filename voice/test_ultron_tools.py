from tools.system_tools import get_system_info


def main() -> None:
    info = get_system_info()

    print("ULTRON TOOL TEST")
    print("================")
    print(f"Operating System : {info['os']}")
    print(f"CPU              : {info['cpu']}")
    print(
        f"RAM              : "
        f"{info['ram_used_gb']} / "
        f"{info['ram_total_gb']} GB"
    )
    print(f"RAM Usage        : {info['ram_percent']}%")


if __name__ == "__main__":
    main()