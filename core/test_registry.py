from core.tool_registry import AVAILABLE_FUNCTIONS, TOOLS


def main() -> None:
    print("REGISTERED ULTRON TOOLS")
    print("=======================")

    registered_names = sorted(AVAILABLE_FUNCTIONS)

    if len(registered_names) != len(TOOLS):
        raise RuntimeError(
            "Tool registry mismatch: the callable tool list and "
            "AVAILABLE_FUNCTIONS do not contain the same number of tools."
        )

    for tool_name in registered_names:
        if not callable(AVAILABLE_FUNCTIONS[tool_name]):
            raise RuntimeError(
                f"Registered tool is not callable: {tool_name}"
            )

        print(f"- {tool_name}")

    print(f"\nRegistry check passed: {len(registered_names)} tools registered.")


if __name__ == "__main__":
    main()
