import asyncio, glob, os, sys, time
from anthropic import AsyncAnthropic

client = AsyncAnthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# Control flow: which model answers is chosen per task, by a small fast model. That's routing (Lesson 3). (The cache belongs to one model, so
# this is decided once per task, not once per step: switching mid-task would start the cache over.)
ROUTER = "claude-haiku-4-5"
TIERS = {                                    # tier -> (model, effort)
    "quick":    ("claude-haiku-4-5", None),
    "standard": ("claude-sonnet-5-5", "medium"),
    "deep":     ("claude-opus-5-5", "high"),
}
MAX_STEPS, MAX_RESULT = 10, 20_000
TOOL_TIMEOUT, AT_ONCE = 30, 4                # seconds a command may run, commands that may run together

def notes():
    # Context: what the agent starts every task knowing. It's the same text every time, which is what lets it be cached.
    files = [f for pattern in ("README.md", "docs/*.md") for f in sorted(glob.glob(pattern))]
    return "\n\n".join(f"## {f}\n\n{open(f).read()}" for f in files) or "(none)"
SYSTEM = [{"type": "text", "text": f"You are quark, an agent whose body is bash. You work in {os.getcwd()}. Be brief.\n\n# Project notes\n\n{notes()}", "cache_control": {"type": "ephemeral"}}]

def cached(messages):
    # A second cache breakpoint, on the end of the conversation: each call pays full price only for what is new since the last one.
    last = messages[-1]
    blocks = [{"type": "text", "text": last["content"]}] if isinstance(last["content"], str) else list(last["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return messages[:-1] + [{"role": last["role"], "content": blocks}]

def trim(text):
    if len(text) <= MAX_RESULT: return text
    return text[:MAX_RESULT // 2] + f"\n[... {len(text) - MAX_RESULT} characters cut ...]\n" + text[-MAX_RESULT // 2:]

async def route(task):
    reply = await client.messages.create(model=ROUTER, max_tokens=10, messages=[{"role": "user", "content":
        "How much model does this task need? quick: one lookup or one simple command. standard: a few steps. "
        "deep: hard reasoning, debugging, or code that must be right. Reply with one word: quick, standard or deep.\n\nTask: " + task}])
    word = next((b.text.strip().lower() for b in reply.content if b.type == "text"), "")
    return word if word in TIERS else "standard"

async def call(messages, tier):
    # Model interface: streamed, so the person reads the answer as it is written, and timed, so you can see it.
    model, effort = TIERS[tier]
    settings = {"output_config": {"effort": effort}} if effort else {}
    start, first = time.time(), None
    async with client.messages.stream(model=model, max_tokens=16384, system=SYSTEM, tools=tools, messages=cached(messages), **settings) as stream:
        async for event in stream:
            if first is None and event.type == "content_block_start": first = time.time() - start
            if event.type == "text": print(event.text, end="", flush=True)
        reply = await stream.get_final_message()
    u = reply.usage
    print(f"\n[{model}: first output after {first or 0:.1f}s, finished after {time.time() - start:.1f}s; "
          f"input {u.input_tokens} new + {u.cache_read_input_tokens} from cache + {u.cache_creation_input_tokens} written to it; output {u.output_tokens}]")
    return reply

gate = asyncio.Semaphore(AT_ONCE)
async def bash(cmd):
    # Output: one command. Many of these run at once; each reports how long it took.
    async with gate:
        start = time.time()
        p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(p.communicate(), TOOL_TIMEOUT)
            text = out.decode(errors="replace") + (f"\n(exit {p.returncode})" if p.returncode else "")
        except TimeoutError:
            p.kill()
            text = f"stopped after {TOOL_TIMEOUT} seconds"
        return trim(text) or "(no output)", time.time() - start

async def main():
    task = " ".join(sys.argv[1:]) or input("> ")
    tier = await route(task)
    print(f"[routed to {tier}: {TIERS[tier][0]}]")
    messages, start, seen = [{"role": "user", "content": task}], time.time(), [0, 0]
    for step in range(1, MAX_STEPS + 1):
        reply = await call(messages, tier)
        seen[0] += reply.usage.cache_read_input_tokens
        seen[1] += reply.usage.input_tokens + reply.usage.cache_read_input_tokens + reply.usage.cache_creation_input_tokens
        messages.append({"role": "assistant", "content": reply.content})
        calls = [b for b in reply.content if b.type == "tool_use"]
        if not calls:
            print(f"[done in {step} steps, {time.time() - start:.1f}s, {seen[0] / max(seen[1], 1):.0%} of input tokens read from the cache]")
            return
        for b in calls: print(f"$ {b.input.get('cmd')}")
        began = time.time()
        done = await asyncio.gather(*(bash(b.input["cmd"]) for b in calls if b.input.get("cmd")))
        together, alone = time.time() - began, sum(took for _, took in done)
        if len(calls) > 1: print(f"[{len(calls)} commands: {together:.1f}s together, {alone:.1f}s one after another]")
        outputs = iter(done)
        results = []
        for b in calls:
            if b.input.get("cmd"): text, failed = next(outputs)[0], False
            else: text, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            print(text)
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": failed})
        messages.append({"role": "user", "content": results})
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

asyncio.run(main())
