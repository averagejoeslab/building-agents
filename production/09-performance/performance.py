import asyncio, glob, os, sys, time
from anthropic import AsyncAnthropic
from typesafe_sdk import AsyncTypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = AsyncAnthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

# Control flow: which model answers is chosen per task, by asking Jev how much work it is. That's routing (Lesson 3). (The cache belongs to
# one model, so this is decided once per task, not once per step: switching mid-task would start the cache over.)
jev = AsyncTypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev, a decision model: answers typed questions, writes no text
TIERS = {                                    # how much work -> (model, effort)
    "lookup": ("claude-haiku-4-5", None),
    "edit":   ("claude-sonnet-5-5", "medium"),
    "work":   ("claude-opus-5-5", "high"),
}
DEFAULT, SURE = "edit", 0.7                  # the tier when Jev can't say, and how confident it must be to choose another
SIZE = Choice(instructions="How much work does the request in `input` need from an agent that works through a shell?", criteria={
    "lookup": "one quick fact or one command: count, list, show, check a version",
    "edit": "a small, clear change to one or two files",
    "work": "several steps of reading, reasoning and changing things, or a design question"})
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

async def size(input):
    # Model interface: one question to a second model. What's done with the answer is control flow's.
    try:
        answer = (await jev.system_one({"input": input}, {"size": SIZE})).choices["size"]
    except Exception as e:                   # TypeSafeError, or anything else the call raises: never stop the task for it
        return DEFAULT, f"no answer from Jev ({type(e).__name__})"
    if answer.confidence < SURE: return DEFAULT, f"Jev: {answer.choice}, {answer.confidence:.2f}, not sure enough"
    return answer.choice, f"Jev: {answer.choice}, {answer.confidence:.2f}"

async def call(messages, tier):
    # Model interface: streamed, so the person reads the answer as it is written, and timed, so you can see it.
    model, effort = TIERS[tier]
    settings = {"output_config": {"effort": effort}} if effort else {}
    start, first = time.time(), None
    async with client.messages.stream(model=model, max_tokens=16384, system=SYSTEM, tools=tools, messages=cached(messages), **settings) as stream:
        async for event in stream:
            if first is None and event.type == "content_block_start": first = time.time() - start
            if event.type == "text": print(event.text, end="", flush=True)
        output = await stream.get_final_message()
    u = output.usage
    print(f"\n[{model}: first output after {first or 0:.1f}s, finished after {time.time() - start:.1f}s; "
          f"input {u.input_tokens} new + {u.cache_read_input_tokens} from cache + {u.cache_creation_input_tokens} written to it; output {u.output_tokens}]")
    return output

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
    input = " ".join(sys.argv[1:]) or read("> ")
    tier, why = await size(input)
    print(f"[routed to {tier}: {TIERS[tier][0]} ({why})]")
    messages, start, seen = [{"role": "user", "content": input}], time.time(), [0, 0]
    for step in range(1, MAX_STEPS + 1):
        output = await call(messages, tier)
        seen[0] += output.usage.cache_read_input_tokens
        seen[1] += output.usage.input_tokens + output.usage.cache_read_input_tokens + output.usage.cache_creation_input_tokens
        messages.append({"role": "assistant", "content": output.content})
        calls = [b for b in output.content if b.type == "tool_use"]
        if not calls:
            print(f"[done in {step} steps, {time.time() - start:.1f}s, {seen[0] / max(seen[1], 1):.0%} of input tokens read from the cache]")
            return
        for b in calls: print(f"$ {b.input.get('cmd')}")
        began = time.time()
        done = await asyncio.gather(*(bash(b.input["cmd"]) for b in calls if b.input.get("cmd")))
        together, alone = time.time() - began, sum(took for _, took in done)
        if len(calls) > 1: print(f"[{len(calls)} commands: {together:.1f}s together, {alone:.1f}s one after another]")
        outputs = iter(done)
        input = []
        for b in calls:
            if b.input.get("cmd"): text, failed = next(outputs)[0], False
            else: text, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            print(text)
            input.append({"type": "tool_result", "tool_use_id": b.id, "content": text, "is_error": failed})
        messages.append({"role": "user", "content": input})
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")

asyncio.run(main())
