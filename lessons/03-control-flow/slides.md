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

### A hands-on course in building agents by building their harness
Lesson 3

<!-- Lessons 1 and 2 gave us the model interface, input and output. Today we put them inside a loop, and that's what turns them into an agent. -->

---

# Lesson 2 runs once, then stops

- Input, call, output, stop
- The model can ask for a tool, and the tool runs
- But the result never goes back to the model
- Something has to decide what happens next

<!-- Lesson 2 was the "run once" shape. A tool's result is input again, but nothing sends it back. That decision is today's primitive. -->

---

# Control flow is the path between the other four

```
person or world ─► input ─► request ─► model interface ─► response ─► output ─► person or world
                     ▲                                                   │
                     └───────────────────── result ──────────────────────┘
```

- Input gathers, the model interface sends, output handles
- A tool's result is input again
- Control flow decides what happens at the end of the path

<!-- Control flow is how information flows between the other four primitives. They all sit inside it: it decides what runs, in what order, and whether to go again. -->

---

# How you arrange them decides what you've built

- **Run once.** Input, call, output, stop. That's Lesson 2.
- **A chat loop.** Call, show the response, hand back to the person, repeat.
- **A workflow.** Your code decides the steps: draft, check, fix.
- **An agent loop.** While the model asks for tools, run them and call again.

<!-- Same four pieces, four different things. A chat loop is a chatbot. Hand back to the person when the agent loop stops asking. -->

---

# The difference is who decides what happens next

- **Workflow:** your code decides
  - predictable and easy to test
  - only handles what you planned for
- **Agent:** the model decides
  - handles what you didn't plan for, and costs you predictability

<!-- There's no correct one. Pick by who should be making the decision about the next step. -->

---

# Control flow sequences and terminates

- **Sequences:** passes what one primitive produced to the next
- **Terminates:** decides when to stop, or when to hand back to a person

A loop with no clear way to end is a bill with no clear way to end.

<!-- Whatever the shape, these are the only two jobs. Termination is the one people forget. -->

---

# quark.py: Lesson 2, plus one loop

```python
chat = len(sys.argv) < 2

# ── control flow ────────────────────────────────────────────────────────────
messages = [{"role": "user", "content": input}]

while True:
    output = call(show, max_tokens=16384, tools=tools, messages=messages).content
    messages.append({"role": "assistant", "content": output})
```

- `chat` is true when nothing came in on the command line
- Each pass of `while True:` is one call to the model
- `messages` carries everything so far: the simplest context, working memory

<!-- Everything above the control flow section is Lesson 2's, with one addition to input: chat. The growing messages list is how a result reaches the next call. Deciding what really goes in it is Lesson 4. -->

---

# Tool results become the next input

```python
    input = []
    for block in output:                                 # output: run tool requests
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, ...)
            print(done.stdout)
            input.append({..., "content": done.stdout or f"(exit {done.returncode})"})
```
(abridged: two long lines cut to `...`; the last one is commented "input: from the world")

<!-- This is Lesson 2's output: show prints the text as it streams, so this loop only runs tool requests. What's new is that the results are collected as input, from the world. -->

---

# No tool request means it's done

```python
    if input:
        messages.append({"role": "user", "content": input})
        continue
    if not chat or (input := read("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": input})
```

- `if input: ... continue` is the agent loop: results go in, call again
- No input from the world is termination: no step count, no magic word
- `chat` gives one loop two modes: run to completion, or hand back with `> `

<!-- With input on the command line, quark runs until the model stops asking for tools, then exits. With none, it's a chat, and /q or Ctrl-D quits. Notice what's missing: a step limit. quark trusts the model to finish. If the model never stops asking, quark never stops. -->

---

# Run it: two calls, one answer

`uv run lessons/03-control-flow/quark.py "which quark.py in the lessons folder is the longest? answer in one sentence"`

```
$ find . -path "*lessons*" -name "quark.py" -exec wc -l {} + | sort -n | tail -5
   12 ./lessons/01-model-interface/quark.py
   38 ./lessons/02-input-and-output/quark.py
   51 ./lessons/03-control-flow/quark.py
  239 ./lessons/04-context/quark.py
  340 total

The longest one is `./lessons/04-context/quark.py`, at 239 lines.
```

<!-- The first call asked for a command. Its result went back, and the second call answered from what it found. Run it with no input to chat with it instead. -->

---

# Control flow can be much more than one loop

- **Its shape:** single call, chat, workflow, agent loop, agents handing off, a loop woken by a message or a schedule
- **When it stops:** model stops asking, step count, spending limit, refusal, a person says stop
- **Who it hands back to:** a person, another program, or no one
- **What runs at once:** one model call, or several

[LangGraph](https://github.com/langchain-ai/langgraph) is a product built around this primitive alone.

<!-- quark runs one agent loop with no limit. In LangGraph you lay out the steps and the paths between them as a graph, and it runs them. -->

---

# control_flow.py stops, and says why

```python
MAX_STEPS = 10
...
for step in range(1, MAX_STEPS + 1):
    ...
    if output.stop_reason == "refusal":
        print("[stopped: the model declined]")
        break
    ...
    if not input:
        print(f"[done in {step} steps]")
        break
    messages.append({"role": "user", "content": input})
else:
    print(f"[stopped: hit the {MAX_STEPS}-step limit]")
```

<!-- It stops in three ways: at MAX_STEPS calls, when the model is done, or when it declines with a refusal, and it says which. It hands back to no one: there's no chat mode. -->

---

# Two runs: done, and out of steps

`uv run lessons/03-control-flow/control_flow.py "which folder in lessons has the most files? answer in one English sentence"`

```
The `02-input-and-output` folder in `lessons` has the most files, with 5.
[done in 2 steps]
```

With `MAX_STEPS` set to 1, it stops before the model sees the result:

```
$ git --version
git version 2.43.0

[stopped: hit the 1-step limit]
```

(first run shortened)

<!-- Two steps: one command, then the answer. With a one-step limit, the same harness stops after the first command. -->

---

# Five workflows come up most

- **Prompt chaining:** a fixed sequence of calls
- **Routing:** one call sorts the input, your code picks the path
- **Parallelization:** calls at the same time, then combined
- **Orchestrator–workers:** one call splits the task, others do the pieces
- **Evaluator–optimizer:** one call produces, another judges, repeat

From Anthropic's [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

<!-- Two things to keep straight when you read it. The augmented LLM isn't control flow: retrieval and memory are context, tools are output. And routing stays control flow even when it picks a cheaper model; Lesson 1's backup model only steps in when the first is down, so it belongs to the model interface. -->

---

# workflow.py: your code decides the order

- Draft, judge, rewrite, judge: no tools, no loop the model steers
- Stops when the judge replies `PASS`, or after three rounds
- One run (shortened):

```
--- draft 1 ---
Agent rigs wrap model calls while tools guide small tasks.

--- evaluator ---
**Fails.** Two words are not five letters long:
...
--- draft 2 ---
Agent frame holds model parts while tools guide small tasks.

[evaluator: pass]
```

<!-- quark.py and control_flow.py are both agents. This is an evaluator–optimizer workflow. The first draft missed, the judging call said exactly why, and the rewrite passed. Every step was one the code laid out in advance. -->

---

# The rule: sequence the four, and decide when to stop

Arranged differently, the same four pieces are a single call, a chatbot, an agent, or a workflow.

<!-- Control flow sequences the other four primitives and decides when to stop. -->

---

# What control flow never does

- Get the request to the model and the response back: **model interface**
- Gather what goes in: **input**
- Handle the response: **output**
- Decide what each request holds, even `messages`: **context**

Control flow only decides what runs, in what order, and when to stop.

<!-- That includes the growing messages list and the prompts in workflow.py: what a request holds is context, not control flow. -->

---

# What's missing: it's an agent that knows nothing

- Not where it is, what day it is, or who it is
- Not what you told it yesterday
- And `messages` grows every pass, until the model can't read it all

Something has to decide what the model sees.

<!-- In a long session messages will outgrow what the model can read. That's context, next. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Context

Lesson 4
