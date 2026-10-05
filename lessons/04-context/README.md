# Lesson 4: Context

> 🎥 **Video:** coming soon

Context is how inputs are presented to the model: who it is, what's happened, what it remembers. By the end of this lesson you'll have [`agent.py`](./agent.py), 40 lines that are quark: an agent that knows where it is, remembers you across sessions, reads its own source, and summarizes itself when its memory fills up.

## What it is

The model knows nothing about this moment except what's in the tokens you send it. Context is the primitive that decides what's in those tokens, before every call.

## Why a harness needs it

Every call starts from nothing. The model doesn't know where it's running, what day it is, who it is, what it did a minute ago, or what you told it last week, unless the harness puts it in front of the model. And the model can only read so many tokens at once: its context window. A session that runs long enough will outgrow it.

## How it works

The mechanism is one sentence: **before every call, assemble what the model should see, and fit it in the space it has.** Two parts:

- **Assemble.** Choose what goes in, and how it's presented.
- **Fit.** When what you'd send is bigger than the context window, something has to give.

Almost everything people build into harnesses is a context component, because almost everything is a way of deciding what the model sees:

- **Instructions:** who the model is, what it's for, how to behave. Usually a system prompt.
- **Working memory:** what's happened in this session. The message list.
- **Episodic memory:** a record of what happened in past sessions.
- **Semantic memory:** facts and lessons that outlast a session: who you are, what you prefer, what went wrong last time.
- **Procedural memory:** how to do things. Recipes, playbooks, skills loaded when they're relevant.
- **Retrieval:** search a store and put what you found in front of the model.
- **Compaction:** when working memory won't fit, replace some of it with a summary.
- **Self-knowledge:** tell the model what it is and how it works.

You don't need all of them. You need the ones your agent needs, built in whatever way fits.

## Show: quark's context

Here's [`agent.py`](./agent.py), with the system prompt shortened to `...` (it's one long line; read it in the file). The loop, input, output and model interface are the ones from Lessons [1](../01-model-interface/), [2](../02-input-and-output/) and [3](../03-control-flow/). What's new is `mechanics()`, `system()`, `system=system()` on the call, and compaction:

```python
import subprocess, sys, os, datetime
from anthropic import Anthropic, BadRequestError

client, MODEL, body = Anthropic(), "claude-sonnet-5-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]
chat, working_memory, drop = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}], 0

while True:
    try:
        if drop > 0:
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
            if drop > len(turns): break
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
            s = next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), "")
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; continue
        with client.messages.stream(model=MODEL, max_tokens=4096, system=system(), tools=body, messages=working_memory) as stream:
            ...  # the same loop body as Lesson 3
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
```

quark's context has five components.

### Working memory

`working_memory` is every message in this session: what you said, what the model said, what it asked for, what came back. It's sent in full on every call, which is how the model "remembers" what it did two passes ago. It's been there since Lesson 1. What makes it a context component is that the harness decides what's in it, and, as you'll see under compaction, when to replace it.

### Instructions and the world: the system prompt

`system()` builds the system prompt, sent as `system=system()` on every call. It's organized as models of what the agent needs to know:

- **Self Model.** Who it is, that its context window is its mind, that bash is its body, and that it works in a loop.
- **World Model.** Where it is (`os.getcwd()`) and when (`datetime.date.today()`).
- **Other Selves Model.** That you exist, and how to reach you.
- **Body Operations.** How to use its one tool well: small actions, escalate only when needed, look before acting.

Two choices to notice:

**The date, not the time.** `cache_control` tells the API to cache this prompt, so later calls don't pay full price to re-read it. A cache only hits if the prompt is identical, and a timestamp would change every second. So quark puts the date in context and tells the model to run `date` if it needs the time. A context choice, shaped by the model interface.

**`system()` is a function, not a constant.** It's rebuilt on every call, so the directory and date are always current.

### Self-knowledge: its own source

`mechanics()` reads quark's own file, and the system prompt ends with it under `# Mechanics`. The model sees the harness it's running in: how the loop works, what happens to a cut-off command, when it gets summarized. The `system()` line is swapped for a placeholder, since the model is already reading the prompt.

### Semantic memory: a file it writes itself

The **Long-term memory** section of the system prompt points quark at `.quark/memory/memory.md` and tells it how to use it: create it if missing, the exact format for an entry, a command for writing one, ways to read it back with `grep` and `tail`, and what's worth writing: who you are, what you prefer, corrections to how it works.

There's no memory code. quark writes and reads the file with the tool it already has. The harness supplies the instructions; the model does the rest through output and input. That's semantic memory: facts that outlast a session, there for the model to look up.

### Fitting: compaction

Working memory grows every pass, and eventually the API refuses it. quark waits for that to happen. The `except BadRequestError` catches "prompt is too long" and sets `drop`. At the top of the next pass, `drop > 0` means summarize:

- `turns` finds where each of your messages starts.
- Working memory too big to send is also too big to summarize, so quark drops the oldest `drop` turns and asks the model to summarize what's left.
- Working memory is replaced by the summary, and the loop goes on.
- If the summary request is too long too, `drop` goes up by one and it tries again with less. If there's nothing left to drop, quark stops.

The choice is *reactive*: quark compacts when the API says the prompt is too long, not before, so it never spends a call on a summary it didn't need. The cost is that the oldest turns are dropped without being summarized at all.

> quark's own version also retries the summary call if the network fails, and lets you interrupt with ESC. Those are hardening, so they're left out here. Everything else is quark, line for line.

## Run it

From the root of the repo:

```bash
uv run lessons/04-context/agent.py
```

Ask it about itself, and tell it something worth remembering:

```
> what are you, and how do you work?
> remember that I prefer short answers
> /q
```

It can describe its own loop, because it's reading its own source. Then run it again and ask what it knows about you. If it wrote that down, it will find it. Look for yourself:

```bash
cat .quark/memory/memory.md
```

## Recap

**The rule:** before every call, context assembles what the model should see and fits it in the space it has. Memory, retrieval, instructions and compaction are all ways of doing that.

**What quark chose:** a system prompt rebuilt every call from models of self, world and other selves, its own source as self-knowledge, a markdown file it manages itself as semantic memory, and reactive compaction.

**What else would have worked:**
- **Proactive compaction.** Summarize at a threshold, before the API refuses. Costs calls you might not have needed.
- **Truncation.** Drop the oldest messages without summarizing. Cheap, and the model forgets.
- **Episodic memory.** Append every message to a log the model can search later.
- **Retrieval.** Embed past messages or documents and fetch the relevant ones each call.
- **Memory the harness manages.** Code that decides what to save and load, instead of leaving it to the model.
- **Skills.** Instructions loaded only when a task needs them, instead of all at once.

## You've built a harness

Control flow, input, context, model interface, output. Five primitives, 40 lines, and an agent that works, remembers, and knows what it is. quark is one set of choices. Now you know what the choices are.

So go the other way. Pick a harness you haven't read. [nanoagent](https://github.com/averagejoeslab/nanoagent) is a good first one: another small agent, written in TypeScript. Or pick a big one. Read it and sort what you find under the five primitives:

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the model see? which memories? how does it fit?
├── model interface   which model, how is it called, what's kept from the reply?
└── output            where do outputs go? which tools, and how are they run?
```

Some things won't fit at first. Ask what each one does. Is it deciding what the model sees? Then it's context, whatever it's called. Is it acting on what the model said? Output. Keep asking until it fits. If you find something that genuinely fits none of the five, I'd like to hear about it.
