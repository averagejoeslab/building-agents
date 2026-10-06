import subprocess, sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def show(event):                                         # output: text, shown as it's written
    if event.type == "text": print(event.text, end="", flush=True)
    if event.type == "content_block_stop" and event.content_block.type == "text": print()

# ── input ───────────────────────────────────────────────────────────────────
def read(prompt):                                        # input: from a person
    while True:
        print(prompt, end="", flush=True)
        line = sys.stdin.readline()
        if not line: return "/q"                         # end of input (Ctrl-D): nothing more is coming
        if line.strip(): return line.rstrip("\n")        # Enter on an empty line: a fresh prompt, as in a terminal
        prompt = "> "
input = " ".join(sys.argv[1:]) or read("> ")
if input == "/q": sys.exit()
chat = len(sys.argv) < 2

# ── control flow ────────────────────────────────────────────────────────────
messages = [{"role": "user", "content": input}]

while True:
    output = call(show, max_tokens=16384, tools=tools, messages=messages).content
    messages.append({"role": "assistant", "content": output})

    input = []
    for block in output:                                 # output: run tool requests
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})  # input: from the world

    if input:
        messages.append({"role": "user", "content": input})
        continue
    if not chat or (input := read("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": input})
