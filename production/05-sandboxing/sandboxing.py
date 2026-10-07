import subprocess, sys, os, atexit

box = f"box-{os.getpid()}"
net = f"{box}-net"

def docker(*args):
    return subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")

docker("network", "create", "--internal", net)           # a network with no way out
up = docker("run", "-d", "--rm", "--name", box, "--network", net, "--memory", "256m", "--pids-limit", "64", "--cap-drop", "ALL", "--read-only", "--tmpfs", "/tmp", "--user", "65534:65534", "python:3.13-slim", "sleep", "infinity")
if up.returncode: sys.exit(f"[no box, so nothing runs: {up.stdout.strip()}]")
atexit.register(lambda: docker("network", "rm", net))
atexit.register(lambda: docker("rm", "-f", box))         # thrown away when the program ends: the box, then its network

def run(cmd):
    print(f"$ {cmd}")
    done = docker("exec", box, "timeout", "-s", "KILL", "5", "sh", "-c", cmd)
    print(f"{done.stdout}(exit {done.returncode})\n")

FETCH = "python3 -c \"import urllib.request as u; print(u.urlopen('http://archive.ubuntu.com/ubuntu/', timeout=10).status)\""
for cmd in sys.argv[1:] or ["id; echo hi > /etc/hello", "sleep 60", "python3 -c 'bytearray(1024**3)'", FETCH]:
    run(cmd)
