import subprocess, sys, os, re, json, time, random, signal
from anthropic import Anthropic, APIConnectionError, APIStatusError
from typesafe_sdk import TypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic(max_retries=0, timeout=120)   # the SDK's own retries are off: this file does them, where you can see them
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]   # tried in order; the first is the one you want
ATTEMPTS, BASE, CAP = 4, 1.0, 20.0                  # tries per model, first wait, longest wait (seconds)
BENCH = 60                                          # seconds a model that just failed is left alone
MAX_STEPS = 10
TOOL_TIMEOUT, MAX_OUT = 20, 4000                    # seconds a command may run, characters of its output kept
CHECKPOINT = ".quark/checkpoint.json"
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, for one question (Lesson 5); no key, no Jev
SURE = 0.8                                          # how confident Jev must be before its answer changes anything
READS = {"cat", "head", "tail", "ls", "wc", "grep", "curl"}   # programs that only look, so running one twice does no harm

class Down(Exception): pass

def retryable(e):
    # Worth trying again: the network, a timeout, "slow down", "try later", overloaded. Not worth it: a bad key, a bad request.
    return isinstance(e, APIConnectionError) or e.status_code in (408, 409, 429) or e.status_code >= 500

def pause(e, attempt):
    # If the server said how long to wait, wait that. Otherwise back off exponentially, with jitter so a crowd of clients doesn't return at once.
    told = getattr(getattr(e, "response", None), "headers", {}).get("retry-after")
    if told and told.isdigit(): return min(float(told), CAP)
    return random.uniform(0.5, 1.0) * min(CAP, BASE * 2 ** attempt)

benched = {}   # model -> time it may be tried again
def ask(**request):
    for model in [m for m in MODELS if benched.get(m, 0) < time.time()] or MODELS:
        for attempt in range(ATTEMPTS):
            try:
                return model, client.messages.create(model=model, **request)
            except (APIConnectionError, APIStatusError) as e:
                if not retryable(e): raise
                what = type(e).__name__
                if attempt == ATTEMPTS - 1:
                    print(f"[{model}: {what}, giving up on it for {BENCH}s]")
                    benched[model] = time.time() + BENCH
                    break
                wait = pause(e, attempt)
                print(f"[{model}: {what}, try {attempt + 1} of {ATTEMPTS}, waiting {wait:.1f}s]")
                time.sleep(wait)
    raise Down()

def run(cmd):
    # Output's side of resilience: a command can hang, print forever, or die. Whatever happens, the model gets a result it can read.
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
    try:
        out, _ = p.communicate(timeout=TOOL_TIMEOUT)
        note = f"\n(exit {p.returncode})" if p.returncode else ""
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)   # the whole group, so the command's children go too
        out, _ = p.communicate()
        note = f"\n(killed: still running after {TOOL_TIMEOUT} seconds)"
        p.returncode = -9
    if len(out) > MAX_OUT: out, note = out[:MAX_OUT], f"\n[output cut at {MAX_OUT} characters]" + note
    return (out + note).strip() or "(no output)", p.returncode != 0

def failure(cmd, out):
    # Jev's question: will this failed command work if it's simply run again? Unsure, or no answer at all, is "unsure" or None: never a retry.
    try: a = jev.system_one({"command": cmd, "result": out}, {"failure": Choice(
        instructions="The command in `command` failed with `result`. What kind of failure is it?",
        criteria={"transient": "likely to work if run again unchanged: network blip, timeout, lock held, rate limit, busy resource",
                  "permanent": "will fail again unchanged: missing file, syntax error, wrong argument, permission denied, failing test",
                  "partial": "it got part of the way: some of its changes may have happened before it failed"})}).choices["failure"]
    except Exception:
        print("[Jev: no answer]")
        return None
    print(f"[Jev: {a.choice}, confidence {a.confidence:.2f}]")
    return a.choice if a.confidence >= SURE else "unsure"

def reads(cmd):
    # Hand-written and strict: one program from READS, no pipes, redirects or chaining, no curl flag that sends or saves. Jev never decides this.
    return cmd.split()[0] in READS and not re.search(r"[|;&<>$`(\n]| -[A-Za-z]*[oOXdTF]|--(data|upload|output|request|form)", cmd)

def save(messages):
    os.makedirs(".quark", exist_ok=True)
    with open(CHECKPOINT + ".tmp", "w") as f: json.dump({"messages": messages}, f, default=lambda b: b.model_dump(exclude_none=True))
    os.replace(CHECKPOINT + ".tmp", CHECKPOINT)   # all of the old file or all of the new one, never half

def resume():
    if not os.path.exists(CHECKPOINT): sys.exit("[nothing to resume]")
    saved = json.load(open(CHECKPOINT))
    messages = saved["messages"]
    if messages[-1]["role"] == "assistant":
        # The model asked for commands and the harness died before the answers were saved. Some may have run. Say so, don't guess.
        lost = [b for b in messages[-1]["content"] if b["type"] == "tool_use"]
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": b["id"], "content": f"interrupted: the harness stopped while this was pending, so it may or may not have run. Check before repeating it: {b['input'].get('cmd')}", "is_error": True} for b in lost]})
    print(f"[resuming: {messages[0]['content'][:60]!r}, {len(messages)} messages]")
    return messages

if sys.argv[1:] == ["resume"]:
    messages = resume()
else:
    input = " ".join(sys.argv[1:]) or read("> ")
    messages = [{"role": "user", "content": input}]

save(messages)
for step in range(1, MAX_STEPS + 1):
    try:
        model, output = ask(max_tokens=16384, tools=tools, messages=messages)
    except Down:
        sys.exit(f"[no model answered. Everything so far is saved (step {step}); run `resilience.py resume` to pick it up]")
    if model != MODELS[0]: print(f"[answered by the backup, {model}]")
    messages.append({"role": "assistant", "content": output.content})
    save(messages)
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    input = []
    for block in output.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            cmd = block.input.get("cmd")
            print(f"$ {cmd}")
            if not cmd or (output.stop_reason == "max_tokens" and block is output.content[-1]):
                out, failed = "your request was cut off at the token limit, so it was not run. Send it again, shorter.", True
            else:
                out, failed = run(cmd)
                kind = failure(cmd, out) if failed else None
                if kind == "transient" and reads(cmd):
                    print(f"[trying once more in {BASE:.0f}s]")
                    time.sleep(BASE)
                    out, failed = run(cmd)
                elif kind in ("partial", "unsure") and not reads(cmd):   # a read can't have partly done anything
                    out += "\n(it may have partly run: check before repeating it)"
            print(out)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": failed})
    if not input:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": input})
    save(messages)
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
    sys.exit()   # keep the checkpoint
os.remove(CHECKPOINT)   # finished, nothing to resume
