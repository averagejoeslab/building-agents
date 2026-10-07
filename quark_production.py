# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, os, re, glob, json, time, datetime, atexit
from anthropic import Anthropic, APIConnectionError, RateLimitError, InternalServerError, OverloadedError, BadRequestError

model = Anthropic(max_retries=3)                         # resilience: retry a request that fails
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]        # resilience: if one keeps failing, try the next
CHEAP = "claude-haiku-4-5"                               # performance: good enough for a summary
bash = {"name": "bash", "description": "Run a shell command",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}
SESSION = os.path.expanduser(f"~/.quark/{os.getcwd().replace('/', '_')}.json")   # persistence: this folder's last session
MEMORY, SKILLS = ".quark/memory.md", ".quark/skills"     # persistence: what quark learned, kept in this folder
BOX = f"quark-{os.getpid()}"                             # safety: the container commands run in
NEVER = re.compile(r"\bsudo\b|rm\s+-\w*[rf]|git\s+push|\.env\b")   # safety: never, whatever the answer
MAX_STEPS = 50                                           # safety: the most steps for one request
RECORD = os.path.expanduser("~/.quark/record.jsonl")     # observability: where each step is written down
MAX_RESULT = 10_000                                      # performance: the most of a command's output to send


# ── input ─────────────────────────────────────────────────────────────────────

def capture_input():
    try:
        return " ".join(sys.argv[1:]) or input("\n> ")  # evaluation: a request can come from the command line
    except (EOFError, KeyboardInterrupt):                # safety: Ctrl-D (or Ctrl-C) at the prompt quits
        sys.exit()


# ── context ───────────────────────────────────────────────────────────────────

def remembered():                                        # persistence: what earlier sessions learned
    facts = open(MEMORY).read() if os.path.exists(MEMORY) else "(nothing yet)"
    skills = "\n".join(f"- {path}: {open(path).readline().strip()}" for path in sorted(glob.glob(f"{SKILLS}/*.md")))
    return f"Facts:\n{facts}\nSkills:\n{skills or '(none yet)'}"


KNOWN = remembered()                                     # performance: read once, so a new fact doesn't restart the cache


def assemble_context(conversation):
    instructions = (f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}.\n"
                    f"Keep facts worth remembering in {MEMORY}, one per line. Save a method you'll need again as "
                    f"{SKILLS}/<name>.md, with a first line saying when to use it.\n{KNOWN}")
    return {"system": instructions, "tools": [bash], "messages": conversation,
            "cache_control": {"type": "ephemeral"}}      # performance: reuse what was already sent


def summarize(conversation):                             # resilience: too long to send, so the older part becomes a summary
    starts = [i for i, message in enumerate(conversation) if message["role"] == "user" and isinstance(message["content"], str)]
    if len(starts) < 2:
        sys.exit("[this request alone is too long to send]")
    older, newer = conversation[:starts[-1]], conversation[starts[-1]:]
    ask = {"role": "user", "content": "Summarize this conversation, keeping what matters for carrying on."}
    summary = model.messages.create(model=CHEAP, max_tokens=2048, tools=[bash], messages=older + [ask])   # performance: a cheaper model
    newer[0] = {"role": "user", "content": f"[earlier, summarized] {summary.content[0].text}\n\n{newer[0]['content']}"}
    record(summarized=len(older))
    return newer


# ── model interface ───────────────────────────────────────────────────────────

def request_response(context, on_each_piece):
    for name in MODELS:
        shown = False
        try:
            with model.messages.stream(model=name, max_tokens=16384, **context) as stream:   # performance: stream the reply
                try:
                    for piece in stream:
                        shown = shown or piece.type == "text"
                        on_each_piece(piece)
                except KeyboardInterrupt:                # safety: with streaming, Ctrl-C stops it mid-sentence
                    return stream.current_message_snapshot
                return stream.get_final_message()
        except (APIConnectionError, RateLimitError, InternalServerError, OverloadedError) as error:
            record(model_failed=name, error=type(error).__name__)
            if shown:
                raise                                    # resilience: half a reply is on screen, so don't start another
            failure = error
    raise failure


# ── output ────────────────────────────────────────────────────────────────────

def start_box():                                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)


def show_text(piece):                                    # performance: words appear as they arrive
    if piece.type == "content_block_start" and piece.content_block.type == "text":
        print("< ", end="", flush=True)
    if piece.type == "text":
        print(piece.text.replace("\n", "\n  "), end="", flush=True)
    if piece.type == "content_block_stop" and piece.content_block.type == "text":
        print()


def run_command(command):
    ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", command],   # resilience: a minute at most
                         capture_output=True, text=True, errors="replace")                # resilience: odd bytes can't crash it
    result = ran.stdout + ran.stderr or "(no output)"
    if ran.returncode == 124:
        result += "\n[stopped: it ran for over a minute]"
    record(command=command, exit=ran.returncode)
    print("  " + "\n  ".join(result.splitlines()[:10]))  # observability: what it did, not just what it ran
    return trim(result)


def trim(result):                                        # performance: keep the start and end of a long result
    if len(result) <= MAX_RESULT:
        return result
    return f"{result[:MAX_RESULT // 2]}\n[... {len(result) - MAX_RESULT} characters cut ...]\n{result[-MAX_RESULT // 2:]}"


def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            command = block.input.get("command", "")
            print(f"$ {command}")
            if response.stop_reason == "max_tokens" and block is response.content[-1]:
                result = "[never ran: the request was cut off]"   # safety: half a command never runs
            elif NEVER.search(command):
                result = "[refused: never allowed]"     # safety: never, whatever anyone answers
                record(command=command, refused="never")
            elif allowed(command):
                result = run_command(command)
            else:
                result = "[refused: the person said no]"
                record(command=command, refused="no")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
    return tool_results


# ── control flow ──────────────────────────────────────────────────────────────

def allowed(command):                                    # safety: nothing else runs without a yes
    return input("  run this? [y/N] ").strip().lower() == "y"


def record(**step):                                      # observability: one line per step, outside the box
    os.makedirs(os.path.dirname(RECORD), exist_ok=True)
    with open(RECORD, "a") as log:
        log.write(json.dumps({"time": datetime.datetime.now().isoformat(timespec="seconds"), **step}) + "\n")


def save(conversation):                                  # persistence: the session outlasts quark
    os.makedirs(os.path.dirname(SESSION), exist_ok=True)
    with open(SESSION, "w") as file:
        json.dump(conversation, file, default=lambda block: block.model_dump(exclude_none=True))


def resume():
    if os.path.exists(SESSION) and input("continue the last session? [y/N] ").strip().lower() == "y":
        return json.load(open(SESSION))
    return []


def stopped(conversation, why):                          # safety: answer what never finished, then hand back
    last = conversation[-1]
    if last["role"] == "assistant":                      # it stopped while commands ran: each needs an answer
        ids = [block.id for block in last["content"] if block.type == "tool_use"]
        if ids:
            conversation.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": i,
                                                              "content": "[stopped before it finished]"} for i in ids]})
    conversation.append({"role": "assistant", "content": f"[{why}]"})
    record(stopped=why)
    print(f"[{why}]")


def control_flow():
    start_box()
    conversation = resume()
    while True:
        if not conversation or conversation[-1]["role"] == "assistant":   # persistence: an unfinished task carries on
            conversation.append({"role": "user", "content": capture_input()})
        try:
            for step in range(MAX_STEPS):
                save(conversation)
                started = time.time()
                try:
                    response = request_response(assemble_context(conversation), show_text)
                except BadRequestError as error:
                    if "prompt is too long" not in str(error):
                        raise
                    conversation = summarize(conversation)
                    continue
                usage = response.usage                   # observability: the tokens come from the end of the stream
                record(model=response.model, seconds=round(time.time() - started, 1), tokens_in=usage.input_tokens,
                       written=usage.cache_creation_input_tokens, cached=usage.cache_read_input_tokens, tokens_out=usage.output_tokens)
                if response.stop_reason is None:         # persistence: a reply cut off is kept as what was said, marked
                    said = "".join(block.text for block in response.content if block.type == "text")
                    conversation.append({"role": "assistant", "content": f"{said}\n[stopped by you]"})
                    record(stopped="stopped by you")
                    print("\n[stopped by you]")
                    break
                conversation.append({"role": "assistant", "content": response.content})
                tool_results = handle_output(response)
                if not tool_results:
                    break                                # done: hand back to the person
                conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
            else:
                stopped(conversation, f"stopped after {MAX_STEPS} steps")
        except KeyboardInterrupt:                        # safety: Ctrl-C stops the command, and everything it started
            subprocess.run(["docker", "exec", BOX, "kill", "-9", "-1"], capture_output=True)
            stopped(conversation, "stopped by you")
        save(conversation)
        if sys.argv[1:]:
            break                                        # evaluation: a request from the command line runs once


control_flow()
