# /// script
# dependencies = ["anthropic"]
# ///
import subprocess, sys, os, json, datetime, atexit
from anthropic import Anthropic

model = Anthropic(max_retries=3)                         # resilience: retry a request that fails
bash = {"name": "bash", "description": "Run a shell command",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}
BOX = f"quark-{os.getpid()}"                             # safety: the container commands run in
RECORD = os.path.expanduser("~/.quark/record.jsonl")     # observability: where each step is written down
SESSION = os.path.expanduser(f"~/.quark/{os.getcwd().replace('/', '_')}.json")   # persistence: this folder's last session
MEMORY = ".quark/memory.md"                              # persistence: what quark learned, kept in this folder


def capture_input():
    return " ".join(sys.argv[1:]) or input("\n> ")      # evaluation: a request can come from the command line


def assemble_context(conversation):
    instructions = (f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}.\n"
                    f"Keep what's worth remembering next time in {MEMORY}, one fact per line. You remember:\n{remembered()}")
    return {"system": instructions, "tools": [bash], "messages": conversation,
            "cache_control": {"type": "ephemeral"}}      # performance: reuse what was already sent


def remembered():                                        # persistence: what earlier sessions learned
    return open(MEMORY).read() if os.path.exists(MEMORY) else "(nothing yet)"


def request_response(context):
    response = model.messages.create(model="claude-sonnet-5-5", max_tokens=16384, **context)
    usage = response.usage
    record(tokens_in=usage.input_tokens, written=usage.cache_creation_input_tokens, cached=usage.cache_read_input_tokens,
           tokens_out=usage.output_tokens)
    return response


def start_box():                                         # safety: a container that sees this folder and nothing else
    here = os.getcwd()
    subprocess.run(["docker", "run", "-d", "--rm", "--name", BOX, "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-e", "HOME=/tmp", "-v", f"{here}:{here}", "-w", here, "python:3.13", "sleep", "infinity"],
                   check=True, capture_output=True)
    atexit.register(subprocess.run, ["docker", "rm", "-f", BOX], capture_output=True)


def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "text":
            print("< " + block.text.replace("\n", "\n  "))
        if block.type == "tool_use":
            command = block.input["command"]
            print(f"$ {command}")
            if allowed(command):                         # safety: in the box; resilience: stopped after a minute
                ran = subprocess.run(["docker", "exec", BOX, "timeout", "60", "sh", "-c", command], capture_output=True, text=True)
                result = ran.stdout + ran.stderr or "(no output)"
                if ran.returncode == 124:
                    result += "\n[stopped: it ran for over a minute]"
                record(command=command, exit=ran.returncode)
            else:
                result = "The person said no."
                record(command=command, refused=True)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
    return tool_results


def allowed(command):                                    # safety: nothing runs without a yes
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


def control_flow():
    start_box()
    conversation = resume()
    while True:
        if not conversation or conversation[-1]["role"] == "assistant":   # an unfinished task carries straight on
            conversation.append({"role": "user", "content": capture_input()})
        while True:
            save(conversation)
            response = request_response(assemble_context(conversation))
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = handle_output(response)
            if not tool_results:
                save(conversation)
                break                                    # done: hand back to the person
            conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
        if sys.argv[1:]:
            break                                        # evaluation: a request from the command line runs once


control_flow()
