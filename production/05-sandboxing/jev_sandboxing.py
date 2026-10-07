import subprocess, sys, os, atexit
from typesafe_sdk import TypeSafeClient, TypeSafeError, Choice
read = input                                             # a person's input; the name input is for whatever comes in

box = f"box-{os.getpid()}"
net = f"{box}-net"
try: jev = TypeSafeClient(timeout=5)                     # Jev, a second model that answers typed questions (reads TYPESAFE_API_KEY)
except TypeSafeError: jev = None                         # no key, no Jev: the box just stays shut
NEEDS = Choice(instructions="To work, what does the shell command in `command` need beyond reading and writing files in the current folder?", criteria={"nothing": "it works inside the current folder with no network", "network": "it must reach the internet or another machine: downloads, installs from a registry, clones, web requests", "outside": "it must write outside the current folder: the home directory, system paths"})
SURE = 0.9                                               # how sure Jev must be before its answer counts

def docker(*args):
    return subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")

docker("network", "create", "--internal", net)           # a network with no way out
up = docker("run", "-d", "--rm", "--name", box, "--network", net, "--memory", "256m", "--pids-limit", "64", "--cap-drop", "ALL", "--read-only", "--tmpfs", "/tmp", "--user", "65534:65534", "python:3.13-slim", "sleep", "infinity")
if up.returncode: sys.exit(f"[no box, so nothing runs: {up.stdout.strip()}]")
atexit.register(lambda: docker("network", "rm", net))
atexit.register(lambda: docker("rm", "-f", box))         # thrown away when the program ends: the box, then its network

def run(cmd):
    print(f"$ {cmd}")
    try: need = jev.system_one({"command": cmd}, {"q": NEEDS}).choices["q"]
    except Exception: need = None                        # no answer: the box stays shut
    if need: print(f"[Jev: {need.choice}, {need.confidence:.2f}]")
    lend = bool(need and need.choice == "network" and need.confidence >= SURE and read("lend it the network for this one command? [y/N] ").lower() == "y")
    if lend: docker("network", "connect", "bridge", box)  # a way out, for this command only
    done = docker("exec", box, "timeout", "-s", "KILL", "5", "sh", "-c", cmd)
    if lend: docker("network", "disconnect", "bridge", box)
    print(f"{done.stdout}(exit {done.returncode})\n")

FETCH = "python3 -c \"import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)\""
for cmd in sys.argv[1:] or ["id; echo hi > /etc/hello", "sleep 60", "python3 -c 'bytearray(1024**3)'", FETCH]:
    run(cmd)
