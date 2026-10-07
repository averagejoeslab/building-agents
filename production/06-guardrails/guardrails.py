import subprocess, sys, re
read = input                                             # a person's input; the name input is for whatever comes in

DENY = {r"\bsudo\b": "no sudo", r"rm\s+-\w*[rf]": "no recursive or forced deletes", r"\.env\b": "secrets are off limits", r"git\s+push": "pushing is the person's call"}
SAFE = {"ls", "cat", "head", "tail", "wc", "grep", "pwd", "date", "echo"}   # programs that only read

def safe(cmd):                                           # only safe programs, and nothing that chains, redirects or expands
    return not re.search(r"[;&<>$`\n(]", cmd) and all((p.split() or [""])[0] in SAFE for p in cmd.split("|"))

def gate(cmd):                                           # deny, allow or ask, before anything runs: None means run it
    for pattern, why in DENY.items():
        if re.search(pattern, cmd): return f"denied: {why}"
    if safe(cmd): return None                            # allowed: it only reads
    try: answer = read("allow it? [y/N] ")
    except EOFError: answer = ""
    return None if answer.strip().lower() == "y" else "the person said no"

for cmd in sys.argv[1:]:                                 # the commands to run, one per argument
    print(f"$ {cmd}")
    if (no := gate(cmd)):
        print(f"[{no}]")
        continue
    print(subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace").stdout, end="")
