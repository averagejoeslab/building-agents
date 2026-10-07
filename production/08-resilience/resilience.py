import subprocess, sys
from anthropic import Anthropic, APIConnectionError, APIStatusError

client = Anthropic(max_retries=2)                        # the SDK tries a failed call twice more, waiting longer each time
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]        # the model you want, then the backup

def call(input):                                         # model interface: when the SDK gives up on a model, try the next one
    for model in MODELS:
        try:
            response = client.messages.create(model=model, max_tokens=1024, messages=[{"role": "user", "content": input}])
            return f"[{model}] " + "".join(block.text for block in response.content if block.type == "text")
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429: raise   # a bad key or a bad request fails on every model
            print(f"[{model}: {type(e).__name__}, after the SDK's retries]")
    return "[no model answered]"

def run(cmd):                                            # output: run a command; when it fails, say so, and never run it again
    done = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    print(done.stdout, end="")
    if not done.returncode: return "[done]"
    return f"[exit {done.returncode}: failed]"

mode, input = sys.argv[1], " ".join(sys.argv[2:])
print(call(input) if mode == "ask" else run(input))
