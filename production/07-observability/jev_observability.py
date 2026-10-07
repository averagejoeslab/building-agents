import subprocess, os, json, time, datetime
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria

client = Anthropic()
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, asked one question about each command
FAILED = Noul(instructions="Does `result` show that the command failed or hit an error?",
    criteria=NoulCriteria(true="The command failed, errored, crashed, was refused or was killed, even if it printed something.",
                          false="The command worked, even if it found nothing or printed a warning."))

def trace(**event):                                      # one JSON line per event, appended, for whoever runs the agent
    with open("traces.jsonl", "a") as f: f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"), **event}) + "\n")

def failed(cmd, result):                                 # Jev's probability that the command failed; None if it can't answer
    try: return round(jev.system_one({"command": cmd, "result": result}, {"q": FAILED}).nouls["q"].noul, 2)
    except Exception: return None

seen = []
for cmd in ["wc -l notes.txt", "grep -n TODO notes.txt", "ls missing.txt | head -1", "sleep 2"]:
    start = time.time()
    done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    trace(event="tool", cmd=cmd, seconds=round(time.time() - start, 2), exit=done.returncode, chars=len(done.stdout), failed=failed(cmd, done.stdout))
    seen.append(f"$ {cmd}\n{done.stdout}(exit {done.returncode})")

start = time.time()
response = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, messages=[{"role": "user", "content": "Which of these commands failed? One sentence.\n\n" + "\n\n".join(seen)}])
trace(event="model", seconds=round(time.time() - start, 2), stop_reason=response.stop_reason, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
print("".join(block.text for block in response.content if block.type == "text"))
