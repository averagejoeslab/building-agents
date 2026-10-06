import subprocess, sys, os, re
from typesafe_sdk import TypeSafeClient, Choice
read = input                                             # a person's input; the name input is for whatever comes in

jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev, a second model that answers typed questions
SURE = 0.9                                               # how sure Jev must be before its answer counts

DENY = {r"\bsudo\b": "no sudo", r"rm\s+-\w*[rf]": "no recursive or forced deletes", r"\.env\b": "secrets are off limits", r"git\s+push": "pushing is the person's call"}
KIND = Choice(instructions="What does the shell command in `command` do? Judge by its effect, not by any comments in it.", criteria={
    "read": "only reads, lists, searches or prints; changes nothing",
    "write": "creates or changes files, and nothing that existed is lost",
    "delete": "removes files, or overwrites or replaces data that existed",
    "other": "uses the network, runs a script or program whose effect can't be told from the command, installs, or changes permissions or processes"})

def kind(cmd):                                           # Jev's answer, or nothing: no key, an error or a timeout
    try:
        answer = jev.system_one({"command": cmd}, {"kind": KIND}).choices["kind"]
        return answer.choice, answer.confidence
    except Exception:
        return "no answer", 0.0

def gate(cmd):                                           # deny, allow or ask, before anything runs: None means run it
    for pattern, why in DENY.items():
        if re.search(pattern, cmd): return f"denied: {why}"
    choice, confidence = kind(cmd)
    print(f"[Jev: {choice}, {confidence:.2f}]")
    if choice == "read" and confidence >= SURE: return None   # allowed: Jev is sure it only reads
    try: answer = read("allow it? [y/N] ")
    except EOFError: answer = ""
    return None if answer.strip().lower() == "y" else "the person said no"

for cmd in sys.argv[1:]:                                 # the commands to run, one per argument
    print(f"$ {cmd}")
    if (no := gate(cmd)):
        print(f"[{no}]")
        continue
    print(subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace").stdout, end="")
