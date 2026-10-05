# Lesson 4: Context

> 🎥 **Video:** coming soon

The model knows nothing about this moment except what's in the request. It doesn't know where it's running, what day it is, who it is, what it did a minute ago, or what you told it last week, unless the harness puts it there. Every call starts from nothing.

Context is how inputs are presented to the model. Input gathers what goes in; context decides what the request actually holds and how it's laid out. Here's where it sits on the path from Lesson 3:

```
person or world ─► input ─► context ─► request ─► model interface ─► response ─► output ─► person or world
                     ▲                                                              │
                     └─────────────────────────── result ───────────────────────────┘
```

Context does two things before every call. It **assembles**: it chooses what goes in the request and how it's presented. And it **fits**: the model can only read so many tokens at once, its context window, so when what you'd send is bigger than that, something has to give.

Almost everything people build into harnesses is a context component, because almost everything is a way of deciding what the model sees:

- **Instructions:** who the model is, what it's for, how to behave. Usually a system prompt.
- **Working memory:** what's happened in this session.
- **Episodic memory:** a record of what happened in past sessions.
- **Semantic memory:** facts that outlast a session: who you are, what you prefer, what went wrong last time.
- **Procedural memory:** how to do things. Recipes, playbooks, skills read when they're relevant.
- **Retrieval:** search a store and put what you found in the request.
- **Compaction:** when working memory won't fit, replace some of it with a summary.
- **Self-knowledge:** tell the model what it is and how it works.

You don't need all of them. You need the ones your agent needs, built in whatever way fits.

## The worked example

Here's Lesson 3's agent with quark's context added. It's the whole of [`quark.py`](./quark.py), with the system prompt shortened to `...`; it's one long line, so read it in the file:

```python
import subprocess, sys, os, datetime
from anthropic import Anthropic, BadRequestError

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... **Where:** {os.getcwd()}\n**When:** {datetime.date.today()} ... ```python\n{mechanics()}\n```", "cache_control": {"type": "ephemeral"}}]

def compact(working_memory, drop):
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if drop > len(turns): sys.exit("[working memory can't be summarized small enough]")
    keep = working_memory[turns[drop]:] if drop < len(turns) else [working_memory[turns[-1]]]
    summary = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, system=system(), messages=keep + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    return [{"role": "user", "content": f"[your prior working memory, summarized] {gist}"}]


task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory, drop = [{"role": "user", "content": task}], 0

while True:
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=4096, system=system(), tools=tools, messages=working_memory)
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        continue

    results = []
    for block in reply.content:
        if block.type == "text":
            print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})

    working_memory.append({"role": "assistant", "content": reply.content})
    if results:
        working_memory.append({"role": "user", "content": results})
        continue
    if not chat or (task := input("\n> ")) == "/q":
        break
    working_memory.append({"role": "user", "content": task})
```

quark's context has five components.

**Working memory.** Lesson 3's `messages` list, renamed `working_memory`, because that's what it is: everything that has happened in this session, sent in full on every call. It's how the model knows what it did two passes ago.

**Instructions: `system()`.** The system prompt, sent as `system=system()` on every call. It's written as models of what quark needs to know: a **Self Model** (who it is, that its context window is its mind, that bash is its body), a **World Model** (where it is, `os.getcwd()`, and when, `datetime.date.today()`), an **Other Selves Model** (that you exist, and how to reach you), and **Body Operations** (how to use its one tool well). It's a function, so the directory and date are current on every call. It holds the date but not the time because `cache_control` asks the API to cache the prompt, and a cache only hits when the prompt is identical; a timestamp would change every second.

**Self-knowledge: `mechanics()`.** quark reads its own file and puts it at the end of the system prompt, under `# Mechanics`, so the model can see the harness it runs in. The `system()` line is swapped for a placeholder, since the model is already reading the prompt.

**Semantic memory: `.quark/memory/memory.md`.** There's no memory code. The system prompt tells quark where the file is, the exact format for an entry, a command for writing one, how to read it back with `grep` and `tail`, and what's worth keeping: who you are, what you prefer, corrections to how it works. quark writes and reads it with the tool it already has.

**Compaction: `compact()`.** When working memory grows past what the model can read, the API refuses the request with "prompt is too long". quark catches that and adds one to `drop`. On the next pass, `compact()` drops the oldest `drop` turns, asks the model to summarize what's left, and replaces working memory with the summary. If even the summary request is too long, `drop` goes up and it tries again with less. This is *reactive*: quark never spends a call on a summary it didn't need, and the cost is that the oldest turns are dropped without being summarized. The summary is one more call through Lesson 1's model interface, and going around again after it is Lesson 3's loop; what's new here is only the decision about what working memory holds. You're unlikely to see it happen: this model can read about a million tokens, so a session has to run very long to fill it. `context.py`, further down, shows compaction with a much smaller limit.

> quark's own version also lets you interrupt it with ESC, and retries the summary if the network fails. Those are hardening, so they're left out here.

## Run it

From the root of the repo, ask it what it is:

```bash
uv run lessons/04-context/quark.py "what are you, and how do you work? three sentences"
```

Here's one run:

```
I'm quark, an AI agent whose only way of acting and observing is a bash shell. That shell lets me read and write files, run programs, and talk to you through terminal output. I work in a loop of observing, thinking and acting. My working memory is my context window, which gets summarized when it fills up. For long-term memory I keep timestamped notes in `.quark/memory/memory.md`, so what I learn can carry over between sessions.
```

It knows its name, its body, its loop and its memory file because they're in its context. Now tell it something:

```bash
uv run lessons/04-context/quark.py "remember that I prefer short answers"
```

```
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; printf '\n## %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> .quark/memory/memory.md && cat >> .quark/memory/memory.md << 'EOF'
- User preference: prefers short answers (keep replies brief)
EOF

I saved that. I'll keep my answers short.
```

That run has ended. A new one starts with empty working memory:

```bash
uv run lessons/04-context/quark.py "what do you know about me?"
```

```
Let me check my memory first.
$ mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md; cat .quark/memory/memory.md
# Quark Memory

## 2026-10-05 21:56:11
- User preference: prefers short answers (keep replies brief)

Not much yet. My memory has one note about you: you prefer short answers.

I know nothing else about you, such as your name, work or projects. I do know that I'm running in `/home/user/building-agents`, but that doesn't tell me much about you.

If you tell me more, I'll save it.
```

Working memory didn't carry anything between the two runs. Semantic memory did.

## Going further

**What else context can be:** quark keeps working memory, a system prompt, its own source, one memory file and reactive compaction. The components listed at the top of this lesson are what context is made of; these are the choices you make when you build them.
- **Who decides what's remembered.** The model, writing it down when it thinks it matters, or harness code that saves and loads on its own.
- **What it retrieves.** Nothing, or documents, code or past messages found by search and put in the request.
- **When it fits.** After the API refuses, or before, by counting tokens against a limit.
- **How it fits.** Summarize old turns, drop them, or cut long tool results down before they're kept.
- **How it's laid out.** One system prompt, or instructions loaded only when a task needs them.

It can be a product on its own. Memory layers like [Mem0](https://github.com/mem0ai/mem0) are this primitive: they store what an agent should remember and hand back what's relevant for each request.

Here's context that does more of that, in [`context.py`](./context.py):

```python
import subprocess, sys, os, json, glob, datetime
from anthropic import Anthropic

client = Anthropic()
MODEL = "claude-sonnet-5-5"
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
LIMIT, KEEP = 50_000, 4_000

def system():
    skills = "\n".join(f"- {p}: {open(p).readline().strip()}" for p in sorted(glob.glob(".quark/skills/*.md"))) or "(none yet)"
    return f"""You are quark, an agent whose body is bash. You're in {os.getcwd()}, and today is {datetime.date.today()}.
Past sessions are logged one message per line in .quark/episodes.jsonl. Search it when the past matters.
Skills: before a task one of these covers, read it with cat and follow it.
{skills}"""

def remember(message):
    os.makedirs(".quark", exist_ok=True)
    with open(".quark/episodes.jsonl", "a") as f: f.write(json.dumps(message, default=lambda b: b.model_dump()) + "\n")

def trim(text):
    return text if len(text) <= KEEP else f"{text[:KEEP // 2]}\n[... {len(text) - KEEP} characters cut ...]\n{text[-KEEP // 2:]}"

def fit(working_memory):
    if client.messages.count_tokens(model=MODEL, system=system(), tools=tools, messages=working_memory).input_tokens < LIMIT: return working_memory
    turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
    if len(turns) < 2: return working_memory
    old, recent = working_memory[:turns[-1]], working_memory[turns[-1]:]
    summary = client.messages.create(model=MODEL, max_tokens=2048, messages=old + [{"role": "user", "content": "Summarize this session so far into a gist that preserves what matters for continuing."}])
    gist = next((b.text for b in summary.content if b.type == "text"), "")
    print(f"[working memory over {LIMIT} tokens: summarized {turns[-1]} messages]")
    return [{"role": "user", "content": f"[earlier in this session, summarized] {gist}"}] + recent

def add(working_memory, message):
    working_memory.append(message); remember(message)

task = " ".join(sys.argv[1:]) or input("> ")
chat = len(sys.argv) < 2
working_memory = []
add(working_memory, {"role": "user", "content": task})

while True:
    working_memory = fit(working_memory)
    reply = client.messages.create(model=MODEL, max_tokens=4096, system=system(), tools=tools, messages=working_memory)
    results = []
    for block in reply.content:
        if block.type == "text": print(block.text)
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(done.stdout)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": trim(done.stdout) or f"(exit {done.returncode})"})
    add(working_memory, {"role": "assistant", "content": reply.content})
    if results:
        add(working_memory, {"role": "user", "content": results}); continue
    if not chat or (task := input("\n> ")) == "/q": break
    add(working_memory, {"role": "user", "content": task})
```

- **Episodic memory.** `add()` writes every message to `.quark/episodes.jsonl` as well as to working memory, and the system prompt says where the log is, so a later session can search it.
- **Procedural memory.** `system()` lists every file in `.quark/skills/` with its first line, and tells the model to read the one that fits before a task it covers.
- **When it fits.** `fit()` counts tokens before every call. Past `LIMIT`, it summarizes everything before your latest message and keeps the rest as it is.
- **How it fits.** `trim()` keeps the start and end of a tool result longer than `KEEP` characters and cuts the middle, before the result goes into working memory.

To try procedural memory, give it a skill:

```bash
mkdir -p .quark/skills
printf 'How to count lines of Python in this repo\n\nUse: find . -name "*.py" -not -path "./.venv/*" | xargs wc -l\nReport the total, then the largest file.\n' > .quark/skills/count-python.md
uv run lessons/04-context/context.py "how many lines of Python are in this repo?"
```

Here's one run:

```
$ cat .quark/skills/count-python.md
How to count lines of Python in this repo

Use: find . -name "*.py" -not -path "./.venv/*" | xargs wc -l
Report the total, then the largest file.

$ find . -name "*.py" -not -path "./.venv/*" | xargs wc -l | sort -n
    9 ./lessons/01-model-interface/quark.py
   13 ./lessons/02-input-and-output/input.py
   16 ./lessons/01-model-interface/model_interface.py
   18 ./lessons/02-input-and-output/output.py
   21 ./lessons/02-input-and-output/quark.py
   21 ./lessons/03-control-flow/workflow.py
   30 ./lessons/03-control-flow/quark.py
   31 ./lessons/03-control-flow/control_flow.py
   48 ./lessons/04-context/quark.py
   56 ./lessons/04-context/context.py
   64 ./lessons/02-input-and-output/input_output.py
  327 total

There are **327 lines** of Python in this repo. I excluded `.venv/`, as the skill says to.

The largest file is `./lessons/02-input-and-output/input_output.py`, at 64 lines.
```

It read the skill, then followed it. That session is now in the episode log, so a new one can find it:

```bash
uv run lessons/04-context/context.py "in a past session, how many lines of Python did you count? one line"
```

```
$ cd /home/user/building-agents; grep -i -n "lines of python\|python" .quark/episodes.jsonl | tail -30; cat .quark/skills/count-python.md
1:{"role": "user", "content": "how many lines of Python are in this repo?"}
2:{"role": "assistant", "content": [{"id": "toolu_01EdcnY4YrCMPrKcMD3hizJV", "caller": {"type": "direct"}, "input": {"cmd": "cat .quark/skills/count-python.md"}, "name": "bash", "type": "tool_use", "toolset_name": null}]}
3:{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_01EdcnY4YrCMPrKcMD3hizJV", "content": "How to count lines of Python in this repo\n\nUse: find . -name \"*.py\" -not -path \"./.venv/*\" | xargs wc -l\nReport the total, then the largest file.\n"}]}
6:{"role": "assistant", "content": [{"citations": null, "text": "There are **327 lines** of Python in this repo. I excluded `.venv/`, as the skill says to.\n\nThe largest file is `./lessons/02-input-and-output/input_output.py`, at 64 lines.", "type": "text"}]}
7:{"role": "user", "content": "in a past session, how many lines of Python did you count? one line"}
How to count lines of Python in this repo

Use: find . -name "*.py" -not -path "./.venv/*" | xargs wc -l
Report the total, then the largest file.

I counted 327 lines of Python in that session, excluding `.venv/`. The largest file was `./lessons/02-input-and-output/input_output.py`, at 64 lines.
```

And with `LIMIT` set to 560 tokens and four questions typed into a chat, `fit()` summarizes before the last one, and the fact from the first survives in the summary:

```
> Noted: your favorite color is green.

> 2+2 = 4.

> 3+3 = 6.

> [working memory over 560 tokens: summarized 6 messages]
Your favorite color is green.

>
```

## What to take away

**The rule:** before every call, context assembles what the request holds and fits it in the space the model has. Memory, retrieval, instructions and compaction are all ways of doing that.

Notice what context never does. Getting the request to the model and the response back is the model interface. When to call, and whether a result goes back around, is control flow. Gathering what goes in is input, and handling the response is output. Context only decides what the request holds and how it fits.

## You've built a harness

Control flow, input, context, model interface, output. Five primitives, 48 lines, and an agent that works, remembers, and knows what it is. quark is one set of choices. Now you know what the choices are.

So go the other way. Pick a harness you haven't read. [nanoagent](https://github.com/averagejoeslab/nanoagent) is a good first one: another small agent, written in TypeScript. Or pick a big one. Read it and sort what you find under the five primitives:

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the request hold? which memories? how does it fit?
├── model interface   where does the request go, and how does the response come back?
└── output            where do outputs go? which tools, and how are they run?
```

Some things won't fit at first. Ask what each one does. Is it deciding what the model sees? Then it's context, whatever it's called. Is it acting on what the model said? Output. Keep asking until it fits. If you find something that genuinely fits none of the five, I'd like to hear about it.
