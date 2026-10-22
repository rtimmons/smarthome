"""Check the real credential path and package import without reading live clients."""

import importlib.metadata
import sys


def main():
    try:
        version = importlib.metadata.version("unifi-mcp-server")
        if version != "0.6.1":
            print("UniFi MCP check failed: unexpected package version.", file=sys.stderr)
            return 1
        # Importing builds the selected server/tool registry, but does not run
        # its transport or call the gateway. Do not print settings or exceptions.
        import src.main  # noqa: F401
    except Exception as error:
        print(
            f"UniFi MCP check failed during package import ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1
    print("UniFi MCP credential lookup and package import OK (0.6.1).")
    print("Desktop MCP initialization and live gateway reads still need verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
