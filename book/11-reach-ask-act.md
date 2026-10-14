## 11. Reach, Ask, Act

### Model interface: reach the mind

We have a model and no way to reach it. The **model interface** sends it a request and brings back the response. For Sonnet, that means an HTTP call to Anthropic's API, which the `anthropic` library wraps. The whole of `1_model_interface.py`:

```python
from anthropic import Anthropic

model = Anthropic()                                    # reads ANTHROPIC_API_KEY from the environment

def request_response(context):
    return model.messages.create(model="claude-sonnet-5-5", max_tokens=16384, **context)

response = request_response({"messages": [{"role": "user", "content": "The tests are failing. Find out why and fix it."}]})
print(response.model_dump_json(indent=2))
```

`context` is a dictionary that will grow as the harness does: for now it holds only `messages`. The response is an object with `content`, a list of blocks, and `stop_reason`, which says why the model stopped (`end_turn` for a finished answer; later, `tool_use` for a request to act). This is Anthropic's **Messages format**, and it's the shape the rest of the harness is written against. What comes back, shortened:

```json
{
  "content": [{"type": "text", "text": "I don't have access to your code, test files, or test output. Nothing came through in your message besides the request. ..."}],
  "model": "claude-sonnet-5-5",
  "stop_reason": "end_turn"
}
```

Tokens in, tokens out. The model can reason about failing tests in general, but it has nothing to reason about. And the request is written into the program: nobody can ask it anything else.

### Input: let someone ask

**Input** captures what comes in. The first kind is a person typing. `2_input.py` adds three lines and uses them:

```python
def capture_input():
    return input("\n> ")

response = request_response({"messages": [{"role": "user", "content": capture_input()}]})
```

Now anyone can type the request:

```
> The tests are failing. Find out why and fix it.
```

```
"I don't have the code or the test output yet, so I can't tell why the tests are failing. Could you share: ..."
```

The same answer. It can only talk. It can't look at a file.

### Output: let it act

The model can only write text, so acting works like this. We *describe* a tool to the model: its name, what it does, and the shape of its arguments as a JSON schema. When the model wants to use it, instead of writing an answer, it emits a `tool_use` block: the tool's name and the arguments, as JSON. **Output** sees the block, carries it out, and collects the result.

```python
bash = {"name": "bash", "description": "Run a shell command",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}},
                         "required": ["command"]}}

def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "text":
            print("< " + block.text.replace("\n", "\n  "))          # words: show them
        if block.type == "tool_use":
            print(f"$ {block.input['command']}")
            ran = subprocess.run(block.input["command"], shell=True, capture_output=True, text=True)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                 "content": ran.stdout + ran.stderr or "(no output)"})
    return tool_results

response = request_response({"tools": [bash], "messages": [{"role": "user", "content": capture_input()}]})
handle_output(response)
```

The description goes to the model in the `tools` field of the context. The model was post-trained to read tool descriptions and to emit `tool_use` blocks whose `input` matches the schema; Sonnet does this natively, and our own model will learn it in Chapter 17. Each result is tagged with the `tool_use_id` of the block that asked for it, so the model can match results to requests when several ran.

```
input ─► model ─► [ TEXT "I'll start by exploring the project" ]
                  [ TOOL_USE id=toolu_01, name=bash, input={command: "pwd; ls -la"} ]
                         │
                         ▼  subprocess.run
                  [ TOOL_RESULT tool_use_id=toolu_01, content="/tmp/shop\nprices.py\ntest_prices.py" ]
```

**Why one tool?** You could give an agent dozens: one to read a file, one to write, one to search, one to run tests. Or one general tool. Through the shell, an agent can do nearly anything a person at that computer can do: read and change files, run programs, run tests, use version control, reach the network. One general tool keeps the harness simple, and a model already knows the shell from training. More tools earn their place when the general one can't do a job, or can't do it safely.

Now it acts:

```
> The tests are failing. Find out why and fix it.
< I'll start by exploring the project and running the tests.
$ pwd; ls -la; git status 2>/dev/null | head
```

And then it stops.

The command ran. It printed a list of files. `handle_output` returned the result. But nothing sent that result back to the model. The model asked to look, the harness looked, and nobody told the model what was seen. It's like opening a door and never looking through it. What came back from acting is new input, from the world rather than from a person, and nothing carries it to the mind.

The fourth part closes that gap.
