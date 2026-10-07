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

Here's a session in a small project: `prices.py` has a `total()` function with a bug, and `test_prices.py` has two tests, one of which fails. `>` is what I typed, `<` is what quark said, and `$` is a command it ran:

```
> The tests are failing. Find out why and fix it.
$ cd /tmp/shop && ls -la && git status 2>&1 | head; git log --oneline 2>&1 | head
$ cd /tmp/shop && cat prices.py test_prices.py; python -m pytest -q 2>&1 | tail -20
< The docstring says discount is a percentage, but the code subtracts it as a flat amount.
$ cd /tmp/shop && sed -i 's|subtotal - discount, 2|subtotal * (1 - discount / 100), 2|' prices.py && python -m unittest -v 2>&1 | tail
< The tests were failing because `total()` in `prices.py` subtracted `discount` as a flat amount. Its docstring, and the `test_ten_percent_off` test, treat it as a percentage. With a discount of 10 on a subtotal of 25, it returned 15 instead of 22.5.
  
  I changed the calculation to `subtotal * (1 - discount / 100)`. Both tests now pass. I ran them with `python -m unittest`, because pytest isn't installed here.

> Commit the fix.
$ cd /tmp/shop && git add prices.py && git commit -q -m "Fix total(): treat discount as a percentage, not a flat amount" && git log --oneline | head -3
< I committed the fix as `416559a`, "Fix total(): treat discount as a percentage, not a flat amount". It includes only `prices.py`.
```

Nobody told it where the bug was or how to run the tests. It looked around, read the code, found the bug, fixed it and checked the fix, one command at a time, each result going back to the model: that's the inner loop. "Commit the fix" needed no explaining, because the whole conversation goes back on every turn.

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
