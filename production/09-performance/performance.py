import subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from anthropic import Anthropic

client = Anthropic()

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
model = "claude-sonnet-5-5"                              # the usual model, whatever the request
print(call(model, input))
call(model, input)                                       # the same request again: its start comes from the cache

checks = ["sleep 2; echo lint ok", "sleep 2; echo types ok", "sleep 2; echo tests ok"]
start = time.time()
for cmd in checks: run(cmd)
print(f"[one at a time: {time.time() - start:.1f}s]")
start = time.time()
with ThreadPoolExecutor() as pool: outputs = list(pool.map(run, checks))
print(", ".join(outputs), f"[at the same time: {time.time() - start:.1f}s]")
