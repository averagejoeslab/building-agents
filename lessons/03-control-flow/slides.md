---
marp: true
theme: default
paginate: true
header: "Lesson 3 · Control flow"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Control flow

### Building agents by building their harness
Lesson 3 of 4

---

# Where we left off

The model asked for `wc -l README.md`.

We ran it and got `71`.

The model never saw it.

---

# Control flow

**How information flows between the other four primitives.**

They all sit inside it.

---

# What it decides

- what runs
- in what order
- whether to go again

---

# The path, with a loop

```
person/world → input → request → model interface → response → output → person/world
                 ↑                                                │
                 └────────────────── tool result ─────────────────┘
```

---

# At the end of the path

Control flow decides one of three things:

- the result goes **back around**
- the **person** gets a turn
- **stop**

---

# Arrangement 1: run once

Lesson 2.

One call, one answer, done.

---

# Arrangement 2: chat loop

Call, show the reply, hand back to the person.

That is a **chatbot**.

---

# Arrangement 3: workflow

**Your code** decides the steps.

Draft, check, fix.

---

# Arrangement 4: agent loop

Call the model.

While it asks for tools: run them, send results back, call again.

Hand back when it stops asking.

---

# No arrangement is correct

They differ in **who decides what's next**.

---

# Workflow: code decides

Predictable and testable.

Handles only the cases you planned.

---

# Agent: the model decides

Handles cases you didn't plan.

Costs predictability.

---

# Control flow does two things

1. **Sequences** the primitives
2. **Terminates**

A loop with no clear end is a bill with no clear end.

---

# Quark's version: `quark.py`

Lesson 2's code inside `while True:`,

plus a `messages` list, the appends that grow it, and a `chat` flag.

30 lines.

---

# Two modes from one flag

```python
chat = len(sys.argv) < 2
```

- Task on the command line: run until the model stops asking, then exit
- No task: chat mode

---

# `while True`: go again

```python
while True:
    reply = client.messages.create(...)
```

Each pass is **one model call**.

---

# `messages.append`: the arrow back

```python
messages.append({"role": "assistant", "content": reply.content})
messages.append({"role": "user", "content": results})
```

Each request carries everything so far.

---

# The growing list is context

A growing `messages` list is the simplest working memory.

It's control flow that appends. Deciding what goes in is **context** (Lesson 4).

---

# `if results: continue`

```python
if results:
    messages.append({"role": "user", "content": results})
    continue
```

These three lines are the **agent loop**.

---

# Termination

No results means the model didn't ask for a tool.

So the model decides to stop.

No step counting. No magic word.

---

# Handing back to the person

```python
if not chat or (task := input("\n> ")) == "/q":
    break
messages.append({"role": "user", "content": task})
```

Chat mode asks for the next task. `/q` quits.

---

# Run it

```bash
uv run lessons/03-control-flow/quark.py \
  "which quark.py in the lessons folder is the longest? \
   answer in one sentence"
```

---

# What happened

1. Call 1: the model asks for `find … -name "quark.py" -exec wc -l {} + | sort -n`; output runs it
2. The result goes back
3. Call 2: the answer is `04-context/quark.py`, 48 lines

Two calls.

---

# The gap: no step limit

Quark trusts the model.

If it never stops asking, quark never stops.

---

# Going further: shape

- single call
- chat loop
- workflow
- agent loop
- agents handing tasks to agents
- a loop that wakes on a message or schedule

---

# Going further: when it stops

- the model stops asking
- N steps
- a spending limit
- the model declines
- the person says stop

---

# Going further: who it hands back to

A person, a program, or no one.

And what runs at the same time: one call, or several.

---

# LangGraph

This primitive as a product.

A graph of steps and the paths between them.

---

# A richer example: `control_flow.py`

Adds the stopping rules.

```python
MAX_STEPS = 10
for step in range(1, MAX_STEPS + 1):
    ...
```

---

# Stop 1: the model declines

```python
if reply.stop_reason == "refusal":
    print("[stopped: the model declined]")
    break
```

---

# Stop 2: the model is done

```python
if not results:
    print(f"[done in {step} steps]")
    break
```

---

# Stop 3: the step limit

```python
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
```

A `for`-`else` runs only if the loop never hit `break`.

---

# No chat mode here

It runs the task, exits, and hands back to no one.

---

# Run `control_flow.py`

Two steps: `[done in 2 steps]`.

With `MAX_STEPS = 1` it stops after the first command, before the model sees the result.

---

# Workflows: code decides

From Anthropic's "Building effective agents."

Five patterns.

---

# Workflow patterns

- **Prompt chaining**: fixed sequence, with checks in code between steps if you want
- **Routing**: one call classifies, code picks the path
- **Parallelization**: split independent parts, or vote on one question
- **Orchestrator-workers**: one call breaks the task down, workers do the pieces
- **Evaluator-optimizer**: one produces, another judges, repeat until pass

---

# Two caveats on that article

- Its "augmented LLM" is retrieval and memory (**context**) plus tools (**output**). It isn't control flow.
- Routing to a cheaper model is a decision about the work. Lesson 1's fallback only covers an outage.

---

# `workflow.py`: evaluator-optimizer

No tools. One helper:

```python
def ask(prompt):  # single call, first text block
```

---

# The draft

```python
draft = ask(f"Do this task. Reply with only the result.\n\n{task}")
```

---

# The loop

```python
for round in range(1, 4):
    print(f"--- draft {round} ---\n{draft}\n")
    verdict = ask(f"Task: … Draft: … reply with only PASS. Otherwise list what to fix.")
    if verdict.strip() == "PASS":
        print("[evaluator: pass]")
        break
    print(f"--- evaluator ---\n{verdict}\n")
    draft = ask(f"Task: … Draft: … Feedback: … Rewrite the draft …")
else:
    print("[stopped: 3 rounds without a pass]")
```

(prompts shortened)

---

# Who decides

**Your code.**

The order is always: draft, judge, rewrite, judge.

---

# Demo

Task: one sentence about agent harnesses.

Every word exactly five letters, at least 8 words.

---

# Demo result

- Draft 1 used "rigs" and "wrap": four letters
- The evaluator listed them
- Draft 2 passed

---

# Agents vs workflows

`quark.py` and `control_flow.py` are **agents**: the model decides.

`workflow.py` is a **workflow**: the code decides.

---

# What to take away

**Rule:** control flow sequences the other four and decides when to stop.

The same pieces, arranged differently, give a single call, a chatbot, an agent, or a workflow.

It never does model interface, input, output, or context. The growing `messages` list and `workflow.py`'s prompts are context.

---

# What's missing

The agent knows nothing: where it is, the date, who it is, what you told it yesterday.

`messages` grows every pass and will outgrow the model's window.

Something must decide what the model sees.

---

<!-- _class: title -->

# Next: Context

Lesson 4 decides what the model sees.
