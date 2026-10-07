import subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic
import os
from typesafe_sdk import TypeSafeClient, Choice

client = Anthropic()
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev: a second model that answers typed questions and writes no text

SIZE = Choice(instructions="How much work does the request in `input` need from an agent that works through a shell?", criteria={"lookup": "one quick fact or one command: count, list, show, check a version", "edit": "a small, clear change to one or two files", "work": "several steps of reading, reasoning and changing things, or a design question"})
TIERS = {"lookup": "claude-haiku-4-5", "edit": "claude-sonnet-5-5", "work": "claude-opus-5-5"}
def route(input):                                        # the smallest model that can do it; unsure means the usual one
    try: size = jev.system_one({"input": input}, {"size": SIZE}).choices["size"]
    except Exception: print(f"[no answer from Jev, so {TIERS['edit']}]"); return TIERS["edit"]
    tier = size.choice if size.confidence >= 0.7 else "edit"
    print(f"[Jev: {size.choice}, {size.confidence:.2f}, so {TIERS[tier]}]")
    return TIERS[tier]

notes = [{"type": "text", "text": open("README.md").read(), "cache_control": {"type": "ephemeral"}}]   # the same long start, marked
def call(model, input):                                  # one call, and where its input tokens came from
    start = time.time()
    output = client.messages.create(model=model, max_tokens=16384, system=notes, messages=[{"role": "user", "content": input}])
    u = output.usage
    print(f"[{time.time() - start:.1f}s: {u.input_tokens} new, {u.cache_creation_input_tokens} written to the cache, {u.cache_read_input_tokens} read from it]")
    return "".join(block.text for block in output.content if block.type == "text")

def run(cmd):                                            # one command, and what it printed
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace").stdout.strip()

input = " ".join(sys.argv[1:])
model = route(input)
print(call(model, input))
call(model, input)                                       # the same request again: its start comes from the cache

checks = ["sleep 2; echo lint ok", "sleep 2; echo types ok", "sleep 2; echo tests ok"]
start = time.time()
for cmd in checks: run(cmd)
print(f"[one at a time: {time.time() - start:.1f}s]")
start = time.time()
with ThreadPoolExecutor() as pool: outputs = list(pool.map(run, checks))
print(", ".join(outputs), f"[at the same time: {time.time() - start:.1f}s]")
