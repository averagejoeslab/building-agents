import sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(**request): return client.messages.create(model=MODEL, **request)

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

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

output = call(max_tokens=16384, tools=tools, messages=[{"role": "user", "content": input}])
print(output.model_dump_json(indent=2))
