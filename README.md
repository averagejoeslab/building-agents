# Building agents

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

An agent has two parts: **a model** and **a harness**.

**Agent = Harness(Model)**

## The model

A model predicts. Tokens go in, it returns the most probable next token, and that token is added to the input. It repeats until it predicts `<eos>`, the end-of-sequence token.

```
            ┌──────────── append ◄────────────┐
            ▼                                 │
TokensIn ─► Model ─► most probable next token ─┤
                                               │
                                     is it <eos>? ── yes ─► TokensOut
```

**TokensOut = Model(TokensIn)**

That's all it does.

## The harness

The harness is everything else. It's been called a framework, a scaffold, a runtime and an orchestration layer, and the industry has mostly settled on *harness*.

Think of the model as an engine. On its own, it just turns. The harness is the rest of the vehicle: it's what makes the engine go somewhere.

Every harness does five things. These are its primitives:

| Primitive | What it does |
|---|---|
| **Input** | captures what comes in |
| **Context** | assembles what the model is shown |
| **Model interface** | requests a response from the model |
| **Output** | handles the response: shows it, or runs it as a tool |
| **Control flow** | decides what happens next: go again, hand back, or stop |

```
┌──────────────────────── control flow ─────────────────────────┐
│                                                                │
│  input ─► context ─► model interface ─► output ─┬─► person     │
│    ▲                    (the model)              │             │
│    └────────────────── a tool's result ──────────┘             │
└────────────────────────────────────────────────────────────────┘
```

## quark

A quark is one of the smallest particles there is. **quark** is the smallest agent: the five primitives and nothing more. It's all in [`quark.py`](./quark.py):

```python
def capture_input():
    return input("\n> ")


def assemble_context(conversation):
    instructions = f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}."
    return {"system": instructions, "tools": [bash], "messages": conversation}


def request_response(context):
    return model.messages.create(model="claude-sonnet-5-5", max_tokens=16384, **context)


def handle_output(response):
    tool_results = []
    for block in response.content:
        if block.type == "text":
            print("< " + block.text.replace("\n", "\n  "))
        if block.type == "tool_use":
            print(f"$ {block.input['command']}")
            ran = subprocess.run(block.input["command"], shell=True, capture_output=True, text=True)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": ran.stdout + ran.stderr or "(no output)"})
    return tool_results


def control_flow():
    conversation = []
    while True:
        conversation.append({"role": "user", "content": capture_input()})
        while True:
            response = request_response(assemble_context(conversation))
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = handle_output(response)
            if not tool_results:
                break                                    # done: hand back to the person
            conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
```

Each function is one primitive, and `control_flow()` holds the other four. The inner loop is what makes it an agent: while the model asks for tools, the results go back and it goes again.

## Run it

You need [uv](https://docs.astral.sh/uv/) and an [Anthropic API key](https://console.anthropic.com/).

```bash
cp .env.example .env        # then put your key in .env
uv run --env-file .env quark.py
```

Here's a session in a folder with one file, `groceries.txt` (milk, eggs, bread). `>` is what I typed, `<` is what quark said, and `$` is a command it ran:

```
> What files are in this folder?
$ ls -la /tmp/groceries
< The folder has one file, `groceries.txt`. It's 16 bytes and was last modified on Oct 7 at 04:09.

> Add coffee to my groceries, and sort the list.
$ cd /tmp/groceries && cat -A groceries.txt
$ cd /tmp/groceries && echo coffee >> groceries.txt && sort -o groceries.txt groceries.txt && cat groceries.txt
< I added coffee to `groceries.txt` and sorted the list alphabetically. It now reads:
  
  - bread
  - coffee
  - eggs
  - milk

> How many items are on it now?
< There are 4 items on the list now: bread, coffee, eggs, and milk.
```

The second request took two commands, one after the other: that's the inner loop. The last answer needed no command at all, because the whole conversation goes back to the model on every turn.

Ctrl-C quits.

> [!WARNING]
> quark runs the model's shell commands without asking. Run it somewhere you can afford to lose.

## From quark to production

quark works, but it isn't ready to run unattended. Getting it there means asking one question of every primitive, in turn:

| Concern | The question |
|---|---|
| Safety | what could do harm here? |
| Resilience | what could fail here? |
| Observability | what should we record here? |
| Performance | what's slow or costly here? |
| Evaluation | how do we know it still works? |

Claude Code, Cursor and every other agent are these same five primitives, hardened in these ways.
