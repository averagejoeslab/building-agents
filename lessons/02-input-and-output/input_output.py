import asyncio, json, os, pathlib, urllib.request
from anthropic import AsyncAnthropic

client = AsyncAnthropic()
BOT = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
tools = [
    {"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
    {"name": "read_file", "description": "Read a text file", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
]

def telegram(method, **params):
    request = urllib.request.Request(f"{BOT}/{method}", data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["result"]

async def receive():
    offset = 0
    while True:
        for update in await asyncio.to_thread(telegram, "getUpdates", offset=offset, timeout=50):
            offset = update["update_id"] + 1
            if text := update.get("message", {}).get("text"):
                await asyncio.to_thread(telegram, "getUpdates", offset=offset, timeout=0)
                return update["message"]["chat"]["id"], text

async def send(chat, text):
    await asyncio.to_thread(telegram, "sendMessage", chat_id=chat, text=text[:4000])

async def bash(cmd):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        return "stopped after 30 seconds", True
    return out.decode(errors="replace") + (f"\n(exit {proc.returncode})" if proc.returncode else ""), False

async def read_file(path):
    try:
        return await asyncio.to_thread(pathlib.Path(path).read_text), False
    except OSError as e:
        return str(e), True

executors = {"bash": lambda args: bash(args["cmd"]), "read_file": lambda args: read_file(args["path"])}

async def execute(block, cut_off):
    if cut_off:
        out, failed = "cut off before it was finished, so it was not run", True
    elif block.name not in executors:
        out, failed = f"no tool named {block.name}", True
    else:
        out, failed = await executors[block.name](block.input)
    return {"type": "tool_result", "tool_use_id": block.id, "content": out or "(no output)", "is_error": failed}

async def main():
    chat, task = await receive()
    reply = await client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=[{"role": "user", "content": task}])
    if words := "\n".join(b.text for b in reply.content if b.type == "text"):
        await send(chat, words)
    calls = [b for b in reply.content if b.type == "tool_use"]
    results = await asyncio.gather(*(execute(b, reply.stop_reason == "max_tokens" and b is reply.content[-1]) for b in calls))
    for call, result in zip(calls, results):
        await send(chat, f"→ {call.name} {json.dumps(call.input)}\n{result['content']}")

asyncio.run(main())
