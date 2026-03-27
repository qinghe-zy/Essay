import json
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client


SERVER_COMMAND = r"C:\Users\33398\.codex\mcp\paper-search-mcp\.venv\Scripts\python.exe"
SERVER_ARGS = ["-m", "paper_search_mcp.server"]
OUTPUT_PATH = Path(r"D:\Essay\verification\paper-search-smoketest.json")


def serialize_content_blocks(blocks):
    serialized = []
    for block in blocks:
        if hasattr(block, "model_dump"):
            serialized.append(block.model_dump(mode="json"))
        else:
            serialized.append(str(block))
    return serialized


async def run_smoketest():
    params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            tools_result = await session.list_tools()
            tool_names = [tool.name for tool in tools_result.tools]

            call_result = await session.call_tool(
                "search_arxiv",
                {"query": "large language models", "max_results": 2},
            )

    payload = {
        "server_name": init_result.serverInfo.name,
        "server_version": init_result.serverInfo.version,
        "tools": tool_names,
        "tool_count": len(tool_names),
        "search_arxiv": {
            "is_error": call_result.isError,
            "structured_content": call_result.structuredContent,
            "content": serialize_content_blocks(call_result.content),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    anyio.run(run_smoketest)
