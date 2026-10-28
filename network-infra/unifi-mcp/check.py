"""Check the real credential path and package import without reading live clients."""

import importlib.metadata
import asyncio
import sys


async def verify_protocol(server):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    async with Client(server.upstream.mcp) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools}
        policy = server.load_policy()
        if names != set(policy["read_tools"] + policy["write_tools"]):
            raise ValueError("Tool registry differs from repository policy")
        await client.call_tool("health_check", {})
        try:
            await client.call_tool("update_network", {"site_id": "default", "dry_run": False})
        except ToolError:
            pass
        else:
            raise ValueError("Unconfirmed write was not rejected")


def main():
    try:
        version = importlib.metadata.version("unifi-mcp-server")
        if version != "0.6.1":
            print("UniFi MCP check failed: unexpected package version.", file=sys.stderr)
            return 1
        # Importing builds the selected server/tool registry, but does not run
        # its transport or call the gateway. Do not print settings or exceptions.
        import server
        server.configure()
        asyncio.run(verify_protocol(server))
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
