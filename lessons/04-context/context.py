import subprocess, sys, os, json, datetime
from anthropic import Anthropic
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
SAVED = ".quark/working_memory.json"

def system():                                            # instructions: built fresh for every call
    return f"You are quark, an agent whose body is bash. You're in {os.getcwd()}, and today is {datetime.date.today()}."

def load():                                              # working memory: what the last session left, or nothing
    if not os.path.exists(SAVED): return []
    with open(SAVED) as f: return json.load(f)

def save(working_memory):                                # written to disk when the session ends
    os.makedirs(os.path.dirname(SAVED), exist_ok=True)
    with open(SAVED, "w") as f: json.dump(working_memory, f, default=lambda b: b.model_dump(exclude_none=True))

input = " ".join(sys.argv[1:]) or read("> ")
working_memory = load() + [{"role": "user", "content": input}]

while True:
    output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, system=system(), tools=tools, messages=working_memory)
    working_memory.append({"role": "assistant", "content": output.content})
    input = []
    for block in output.content:
        if block.type == "text": print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            print(done.stdout)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    if not input: break
    working_memory.append({"role": "user", "content": input})

save(working_memory)
