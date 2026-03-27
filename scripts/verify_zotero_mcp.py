import json
import subprocess
import time
from pathlib import Path

import anyio
import httpx
from mcp import ClientSession, StdioServerParameters, stdio_client


SERVER_COMMAND = r"C:\Users\33398\.codex\mcp\zotero-mcp\.venv\Scripts\zotero-mcp.exe"
SERVER_ARGS = []
SERVER_ENV = {"ZOTERO_LOCAL": "true"}
ZOTERO_EXE = Path(r"C:\Program Files\Zotero\zotero.exe")
API_PROBE_URL = "http://127.0.0.1:23119/api/users/0/items?limit=1"
OUTPUT_PATH = Path(r"D:\Essay\verification\zotero-smoketest.json")


def serialize_content_blocks(blocks):
    serialized = []
    for block in blocks:
        if hasattr(block, "model_dump"):
            serialized.append(block.model_dump(mode="json"))
        else:
            serialized.append(str(block))
    return serialized


def ensure_zotero_api():
    launched = False
    process = None
    probe = {
        "launched_zotero": False,
        "api_ready": False,
        "attempts": [],
    }

    if ZOTERO_EXE.exists():
        try:
            process = subprocess.Popen([str(ZOTERO_EXE)])
            launched = True
            probe["launched_zotero"] = True
            probe["launched_pid"] = process.pid
        except Exception as exc:
            probe["launch_error"] = str(exc)

    for _ in range(15):
        try:
            response = httpx.get(API_PROBE_URL, timeout=5.0)
            probe["attempts"].append({"status_code": response.status_code})
            if response.status_code in (200, 403):
                probe["api_ready"] = True
                break
        except Exception as exc:
            probe["attempts"].append({"error": str(exc)})
        time.sleep(2)

    return probe, process, launched


async def run_smoketest():
    api_probe, launched_process, launched = ensure_zotero_api()
    params = StdioServerParameters(
        command=SERVER_COMMAND,
        args=SERVER_ARGS,
        env=SERVER_ENV,
    )

    payload = {"api_probe": api_probe}

    try:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()
                tool_names = [tool.name for tool in tools_result.tools]

                call_result = await session.call_tool(
                    "zotero_search_items",
                    {"query": "test", "qmode": "everything", "limit": 3},
                )

        payload.update(
            {
                "server_name": init_result.serverInfo.name,
                "server_version": init_result.serverInfo.version,
                "tools": tool_names,
                "tool_count": len(tool_names),
                "zotero_search_items": {
                    "is_error": call_result.isError,
                    "structured_content": call_result.structuredContent,
                    "content": serialize_content_blocks(call_result.content),
                },
            }
        )
    except Exception as exc:
        payload["fatal_error"] = str(exc)
    finally:
        if launched and launched_process is not None:
            try:
                launched_process.terminate()
            except Exception:
                pass

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    anyio.run(run_smoketest)
