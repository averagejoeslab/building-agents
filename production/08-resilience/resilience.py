import subprocess, sys, os, time
from anthropic import Anthropic, APIConnectionError, APIStatusError
from typesafe_sdk import TypeSafeClient, Choice

client = Anthropic(max_retries=2)                        # the SDK tries a failed call twice more, waiting longer each time
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]        # the model you want, then the backup
jev = TypeSafeClient(timeout=5) if os.environ.get("TYPESAFE_API_KEY") else None   # Jev answers typed questions (Lesson 5)
SURE = 0.9                                               # how sure Jev must be before its answer changes anything

def call(input):                                         # model interface: when the SDK gives up on a model, try the next one
    for model in MODELS:
        try:
            response = client.messages.create(model=model, max_tokens=1024, messages=[{"role": "user", "content": input}])
            return f"[{model}] " + "".join(block.text for block in response.content if block.type == "text")
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise   # a bad key or a bad request fails on every model
            print(f"[{model}: {type(e).__name__}, after the SDK's retries]")
    return "[no model answered]"

FAILURE = Choice(instructions="The command in `command` failed with `result`. What kind of failure is it?",
    criteria={"transient": "likely to work if run again unchanged: a network blip, a timeout, a lock held, a rate limit, a busy resource",
              "permanent": "will fail again unchanged: a missing file, a syntax error, a wrong argument, permission denied, a failing test",
              "partial": "it got part of the way: some of its changes may have happened before it failed"})
KIND = Choice(instructions="Does the shell command in `command` only read?",
    criteria={"read": "only reads, lists, searches, queries or prints; changes nothing", "change": "creates, changes or removes something, or its effect can't be told from the command"})
def sure(answer, choice): return answer.choice == choice and answer.confidence >= SURE

def run(cmd):                                            # output: run a command; when it fails, ask Jev whether trying again can help
    for attempt in (1, 2):
        done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        print(done.stdout, end="")
        if not done.returncode: return "[done]"
        try: answers = jev.system_one({"command": cmd, "result": done.stdout[-4000:]}, {"failure": FAILURE, "kind": KIND}).choices
        except Exception: return f"[exit {done.returncode}. Jev: no answer, so no second try]"   # no key, an error or a time-out
        why, kind = answers["failure"], answers["kind"]
        print(f"[exit {done.returncode}. Jev: {why.choice} {why.confidence:.2f}, {kind.choice} {kind.confidence:.2f}]")
        if attempt == 2 or not (sure(why, "transient") and sure(kind, "read")): break   # only a read is safe to run twice
        print("[a failure that passes: trying once more]"); time.sleep(1)
    return "(it may have partly run: check before repeating it)" if sure(why, "partial") else "[failed]"

mode, input = sys.argv[1], " ".join(sys.argv[2:])
print(call(input) if mode == "ask" else run(input))
