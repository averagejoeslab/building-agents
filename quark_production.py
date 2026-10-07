# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, os, re, json, time, datetime, atexit, tempfile
from anthropic import Anthropic, APIConnectionError, RateLimitError, InternalServerError, OverloadedError, BadRequestError

model = Anthropic(max_retries=3)                    # resilience: the SDK retries a failed request three times
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]   # resilience: if one model keeps failing, try the next
bash = {"name": "bash", "description": "Run a shell command",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}
BOX = f"quark-{os.getpid()}"                        # safety: the container commands run in
READERS = {"cd", "ls", "cat", "pwd", "head", "tail", "grep", "wc", "find", "echo", "git status", "git log", "git diff", "git show"}
MAX_STEPS = 50                                      # safety: most steps per request
MAX_RESULT = 10_000                                 # performance: most characters of a command's output to send
RECORD = os.path.expanduser("~/.quark/record.jsonl")                         # observability: outside the box, for you
SAVED = os.path.expanduser(f"~/.quark/{os.getcwd().replace('/', '_')}.json")  # resilience: this folder's unfinished work


# ── input ─────────────────────────────────────────────────────────────────────

def capture_input():
    try:
        return input("\n> ")
    except EOFError:                                 # resilience: Ctrl-D means nothing more is coming
        return None

# ── context ───────────────────────────────────────────────────────────────────

def assemble_context(conversation):
    instructions = f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}."
    return {"system": instructions, "tools": [bash], "messages": cached(conversation)}


def cached(conversation):                # performance: mark the end, so the next request reuses everything before it
    last = dict(conversation[-1])
    blocks = last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
    last["content"] = blocks[:-1] + [{**blocks[-1], "cache_control": {"type": "ephemeral"}}]
    return conversation[:-1] + [last]


def make_room(conversation):             # resilience: too long to send, so drop the oldest exchange
    starts = [i for i, message in enumerate(conversation) if message["role"] == "user" and isinstance(message["content"], str)]
    if len(starts) < 2:
        raise SystemExit("[this request alone is too long to send]")
    del conversation[:starts[1]]

# ── model interface ───────────────────────────────────────────────────────────

def request_response(context, on_each_piece):
    for name in MODELS:
        try:
            with model.messages.stream(model=name, max_tokens=16384, **context) as stream:
                for piece in stream:
                    on_each_piece(piece)
                return stream.get_final_message()
        except (APIConnectionError, RateLimitError, InternalServerError, OverloadedError) as error:
            record("model failed", model=name, error=type(error).__name__)
            failure = error
    raise failure

# ── output ────────────────────────────────────────────────────────────────────

def start_box():                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)


def show_text(piece):                    # performance: words appear as they arrive
    if piece.type == "content_block_start" and piece.content_block.type == "text":
        print("< ", end="", flush=True)
    if piece.type == "text":
        print(piece.text.replace("\n", "\n  "), end="", flush=True)
    if piece.type == "content_block_stop" and piece.content_block.type == "text":
        print()


def trim(result):                        # performance: keep the start and end of a long result
    if len(result) <= MAX_RESULT:
        return result
    half = MAX_RESULT // 2
    return f"{result[:half]}\n[... {len(result) - MAX_RESULT} characters cut ...]\n{result[-half:]}"


def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            print(f"$ {block.input['command']}")
            if not permitted(block.input["command"]):
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": "The person said no.", "is_error": True})
                record("refused", command=block.input["command"])
                continue
            # resilience: a hung command is stopped after a minute, and odd bytes can't crash quark
            ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", block.input["command"]],
                                 capture_output=True, text=True, errors="replace")
            record("command", command=block.input["command"], exit=ran.returncode)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": trim(ran.stdout + ran.stderr) or "(no output)"})
    return tool_results

# ── control flow ──────────────────────────────────────────────────────────────

def permitted(command):                  # safety: reading runs; anything else asks first
    return reads_only(command) or input("  run this? [y/N] ").strip().lower() == "y"


def reads_only(command):                 # safety: every step is a known reader, and nothing is written
    quiet = command.replace("2>&1", "").replace("2>/dev/null", "")
    if re.search(r"[<>`$]|-exec|-delete", quiet):
        return False
    for step in re.split(r"&&|\|\||[;|]", quiet):
        words = step.split()
        if not words or (words[0] not in READERS and " ".join(words[:2]) not in READERS):
            return False
    return True


def record(event, **details):            # observability: one line per step, for the person running quark
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "a") as log:
        log.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), "event": event, **details}) + "\n")


def save(conversation):                  # resilience: so a crash loses nothing
    with open(SAVED, "w") as file:
        json.dump(conversation, file, default=lambda block: block.model_dump(exclude_none=True))


def resume():                            # resilience: pick up unfinished work
    if os.path.exists(SAVED) and input("pick up where you left off? [y/N] ").strip().lower() == "y":
        return json.load(open(SAVED))
    return []


def forget():                            # resilience: a clean exit leaves nothing to pick up
    if os.path.exists(SAVED):
        os.remove(SAVED)


def control_flow():
    start_box()
    one_shot = sys.argv[1:] and iter([" ".join(sys.argv[1:])])   # a request on the command line: do it, then stop
    conversation = [] if one_shot else resume()
    while True:
        if not conversation or conversation[-1]["role"] == "assistant":
            next_input = next(one_shot, None) if one_shot else capture_input()
            if next_input is None:
                forget()
                break
            conversation.append({"role": "user", "content": next_input})
            record("input", text=next_input)
        for step in range(MAX_STEPS):
            save(conversation)
            started = time.time()
            try:
                response = request_response(assemble_context(conversation), show_text)
            except BadRequestError as error:
                if "prompt is too long" not in str(error):
                    raise
                make_room(conversation)
                continue
            usage = response.usage
            record("response", seconds=round(time.time() - started, 1), tokens_in=usage.input_tokens,
                   written=usage.cache_creation_input_tokens, cached=usage.cache_read_input_tokens,
                   tokens_out=usage.output_tokens, stop=response.stop_reason)
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = handle_output(response)
            if not tool_results:
                record("decision", next="hand back")
                break                                    # done: hand back to the person
            record("decision", next="go again")
            conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
        else:
            record("decision", next="step limit")
            print(f"[stopped after {MAX_STEPS} steps]")
            conversation.append({"role": "assistant", "content": f"[stopped after {MAX_STEPS} steps]"})


# ── evaluation: outside the harness ──────────────────────────────────────────

PROJECT = {                                              # a small project with one bug, made fresh for every case
    "prices.py": 'def total(items, discount=0):\n    """Add up (price, quantity) pairs, then take off a percentage discount."""\n'
                 '    subtotal = sum(price * quantity for price, quantity in items)\n    return round(subtotal - discount, 2)\n',
    "test_prices.py": "import unittest\nfrom prices import total\n\n\nclass TestTotal(unittest.TestCase):\n"
                      "    def test_no_discount(self):\n        self.assertEqual(total([(10, 2), (5, 1)]), 25)\n\n"
                      "    def test_ten_percent_off(self):\n        self.assertEqual(total([(10, 2), (5, 1)], discount=10), 22.5)\n",
}
CASES = [                                                # what to ask, and how to tell from the files whether it was done
    {"ask": "The tests are failing. Find out why and fix it.",
     "check": "python3 -m unittest -q && git diff --quiet HEAD -- test_prices.py"},
    {"ask": "What does total() return for an empty basket? Don't change anything.",
     "check": 'test -z "$(git status --porcelain | grep -v __pycache__)"'},
]


def evaluate():                          # evaluation: run quark on known tasks; check the result, not what it says
    passed = 0
    for case in CASES:
        where = tempfile.mkdtemp()
        for name, text in PROJECT.items():
            open(os.path.join(where, name), "w").write(text)
        subprocess.run("git init -q && git add . && git -c user.name=quark -c user.email=quark@example.com commit -qm start",
                       shell=True, cwd=where)
        subprocess.run([sys.executable, __file__, case["ask"]], cwd=where, input="y\n" * 20, capture_output=True, text=True)
        ok = subprocess.run(case["check"], shell=True, cwd=where, capture_output=True).returncode == 0
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {case['ask']}")
    print(f"{passed} of {len(CASES)} passed")


if sys.argv[1:] == ["--eval"]:
    evaluate()
else:
    control_flow()
