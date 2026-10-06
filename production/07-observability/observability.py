import subprocess, sys, os, json, time, uuid, datetime
from collections import defaultdict
from contextlib import contextmanager
from anthropic import Anthropic
from typesafe_sdk import TypeSafeClient, Noul, NoulCriteria
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # a second model, asked one question about each tool result
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
MAX_STEPS = 10
LOG = ".quark/spans.jsonl"
PRICE = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}  # dollars per million tokens: example rates, use your provider's
RUN, SPANS = uuid.uuid4().hex[:8], []
SURE = 0.9                                               # count a tool as failed when Jev is this sure
ERROR = {"error": Noul(instructions="Does `result` show that the command failed or hit an error?",
    criteria=NoulCriteria(true="The command failed, errored, crashed, was refused or was killed, even if it printed something.",
                          false="The command worked, even if it found nothing or printed a warning."))}

@contextmanager
def span(kind, parent=None, **attrs):
    s = {"run": RUN, "span": uuid.uuid4().hex[:6], "parent": parent, "kind": kind, "start": datetime.datetime.now().isoformat(timespec="seconds"), **attrs}
    began = time.time()
    try:
        yield s
    except BaseException as e:
        s["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        s["seconds"] = round(time.time() - began, 2)
        SPANS.append(s)
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f: f.write(json.dumps(s) + "\n")

def failed(cmd, result):
    try:
        return round(jev.system_one({"command": cmd, "result": result}, ERROR).nouls["error"].noul, 2)
    except Exception:
        return None                                      # no verdict: the span just says so

def cost(usage):
    return round(sum(usage[k] * PRICE[k] for k in PRICE) / 1_000_000, 6)

def row(spans):
    run = next((s for s in spans if s["kind"] == "run"), {})
    calls = [s for s in spans if s["kind"] == "model" and "cost" in s]
    ran = [s for s in spans if s["kind"] == "tool"]
    sent = sum(c["input"] + c["cache_read"] + c["cache_write"] for c in calls)
    problems = sum(t.get("exit") != 0 for t in ran) + sum("error" in s for s in spans)
    flagged = sum((s.get("failed") or 0) >= SURE for s in spans if s["kind"] == "jev")
    return f"{spans[0]['run']}  {run.get('status', 'crashed'):<10} {len(calls):>5} {len(ran):>5} {problems:>5} {flagged:>4} {sum(s['seconds'] for s in calls + ran):>6.1f}s {sent:>8} {sum(c['output'] for c in calls):>6} {sum(c['cache_read'] for c in calls) / max(sent, 1):>6.0%} ${sum(c['cost'] for c in calls):>8.4f}  {run.get('task', '')[:40]}"

HEADER = "run       status     calls tools  prob.  jev   time     in    out  cached     cost  task"

if sys.argv[1:2] == ["report"]:
    runs = defaultdict(list)
    for line in open(LOG):
        runs[json.loads(line)["run"]].append(json.loads(line))
    print(HEADER)
    for spans in runs.values(): print(row(spans))
    sys.exit()

input = " ".join(sys.argv[1:]) or read("> ")
messages = [{"role": "user", "content": input}]

with span("run", task=input) as run:
    for step in range(1, MAX_STEPS + 1):
        with span("model", run["span"], step=step) as m:
            output = client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, tools=tools, messages=messages)
            u = output.usage
            m.update(stop_reason=output.stop_reason, input=u.input_tokens, output=u.output_tokens, cache_read=u.cache_read_input_tokens, cache_write=u.cache_creation_input_tokens)
            m["cost"] = cost(m)
        print(f"[step {step}: model {m['seconds']}s, {m['input'] + m['cache_read'] + m['cache_write']} tokens in, {m['output']} out, ${m['cost']:.4f}]")
        messages.append({"role": "assistant", "content": output.content})
        if output.stop_reason == "refusal":
            run["status"] = "declined"
            break
        input = []
        for block in output.content:
            if block.type == "text":
                print(block.text)
            if block.type == "tool_use":
                print(f"$ {block.input['cmd']}")
                with span("tool", run["span"], step=step, cmd=block.input["cmd"]) as t:
                    done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                    t.update(exit=done.returncode, chars=len(done.stdout))
                result = done.stdout or f"(exit {done.returncode})"
                with span("jev", t["span"], step=step) as j:     # its own span, so the tool's seconds stay the tool's
                    j["failed"] = failed(block.input["cmd"], result)
                print(done.stdout)
                print(f"[step {step}: tool {t['seconds']}s, exit {t['exit']}, Jev: failed {j['failed']}]")
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        if not input:
            run["status"] = "done"
            break
        messages.append({"role": "user", "content": input})
    else:
        run["status"] = "step limit"

print(HEADER)
print(row(SPANS))
