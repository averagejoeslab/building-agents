import subprocess, sys, re, collections
from anthropic import Anthropic
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS, MAX_DOLLARS, MAX_REPEATS = 10, 0.05, 3
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's

# The policy: what may run without asking, and what may never run.
ALLOWED = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo", "cd", "du", "df", "stat", "file", "uniq", "whoami"}
DENIED = {
    r"\bsudo\b": "no sudo",
    r"\.env\b": "secrets files are off limits",
    r"rm\s+-\w*[rf]": "no recursive or forced deletes",
    r"git\s+push": "pushing is the person's call",
    r"(curl|wget)[^|]*\|\s*(ba)?sh": "no running downloaded scripts",
}

def programs(cmd):
    return [p.split()[0] for p in re.split(r"&&|\|\||[;|\n]", cmd) if p.split()]

def verdict(cmd):
    for pattern, why in DENIED.items():
        if re.search(pattern, cmd): return "deny", why
    if re.search(r"[<>`$]", cmd): return "ask", "it redirects, or expands something I can't see"
    for p in programs(cmd):
        if p not in ALLOWED: return "ask", f"{p} isn't on the allowed list"
    return "allow", ""

def ask(cmd, why):
    try: answer = read(f"allow `{cmd}`? ({why}) [y]es, [a]lways, or say why not: ").strip()
    except EOFError: answer = ""
    if answer.lower() in ("y", "yes"): return None
    if answer.lower() in ("a", "always"):
        ALLOWED.update(programs(cmd))
        return None
    return f"the person said no: {answer or 'no'}"

def guard(cmd):
    action, why = verdict(cmd)
    if action == "deny": return f"blocked by policy: {why}"
    if action == "ask": return ask(cmd, why)

def cost(u):
    return (u.input_tokens * PRICE["input"] + u.output_tokens * PRICE["output"] + u.cache_read_input_tokens * PRICE["cache_read"] + u.cache_creation_input_tokens * PRICE["cache_write"]) / 1_000_000

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]
spent, asked = 0.0, collections.Counter()

for step in range(1, MAX_STEPS + 1):
    if spent >= MAX_DOLLARS:
        print(f"[stopped: spent ${spent:.4f}, over the ${MAX_DOLLARS} budget]")
        break
    if asked and max(asked.values()) >= MAX_REPEATS:
        print(f"[stopped: asked for the same command {MAX_REPEATS} times]")
        break
    input, replied = [], False
    try:
        output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
        replied = True
        messages.append({"role": "assistant", "content": output.content})
        spent += cost(output.usage)
        if output.stop_reason == "refusal":
            print("[stopped: the model declined]")
            break
        for block in output.content:
            if block.type == "text":
                print(block.text)
            if block.type == "tool_use":
                cmd = block.input["cmd"]
                print(f"$ {cmd}")
                asked[cmd] += 1
                if (no := guard(cmd)):
                    print(f"[{no}]")
                    input.append({"type": "tool_result", "tool_use_id": block.id, "content": no, "is_error": True})
                    continue
                done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                print(done.stdout)
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
    except KeyboardInterrupt:
        print("\n[interrupted]")
        if replied:
            answered = {r["tool_use_id"] for r in input}
            input += [{"type": "tool_result", "tool_use_id": b.id, "content": "interrupted by the person", "is_error": True} for b in output.content if b.type == "tool_use" and b.id not in answered]
        try: say = read("what now? (blank to stop) > ").strip()
        except EOFError: say = ""
        if not say:
            print("[stopped: interrupted]")
            break
        messages.append({"role": "user", "content": input + [{"type": "text", "text": say}] if replied else say})
        continue
    if not input:
        print(f"[done in {step} steps, ${spent:.4f}]")
        break
    messages.append({"role": "user", "content": input})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
