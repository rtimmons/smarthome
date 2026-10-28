"""Repository policy boundary around the pinned upstream stdio server."""

from pathlib import Path

from fastmcp.server.middleware import Middleware
from src import main as upstream
from policy import guard, load_policy

DIRECTORY = Path(__file__).resolve().parent


class PolicyMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        args = guard(context.message.name, context.message.arguments, load_policy())
        return await call_next(context.copy(message=context.message.model_copy(update={"arguments": args})))

    async def on_list_tools(self, context, call_next):
        policy = load_policy()
        tools = await call_next(context)
        return [tool for tool in tools if tool.name in policy["read_tools"] + policy["write_tools"]]


def configure():
    load_policy()
    upstream.mcp.instructions = (DIRECTORY / "POLICY.md").read_text()
    upstream.mcp.add_middleware(PolicyMiddleware())


if __name__ == "__main__":
    configure()
    upstream.main()
