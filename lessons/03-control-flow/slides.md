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

# control_flow.py: a workflow, where your code decides

```python
def workflow(input):
    draft = ask(f"Do this task. Reply with only the result.\n\n{input}")
    review = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\n...")
    output = ask(f"Task:\n{input}\n\n...Rewrite the draft...")
```
(abridged: the prints and most of each prompt cut)

- Three calls, always in the same order: draft, review, rewrite
- The model writes every word, but never picks the next step

<!-- Here's the idea with nothing around it: who decides the next step. control_flow.py runs it both ways. call() and ask() are the model interface cut down to one line each. In workflow(), nothing the model says can add a step or skip one. -->

---

# control_flow.py: an agent, where the model decides

```python
    while True:
        output = call(messages, tools=tools)
        messages.append({"role": "assistant", "content": output})
        ...
                done = subprocess.run(block.input["cmd"], shell=True, ...)
                input.append({..., "content": done.stdout or f"(exit {done.returncode})"})
        if not input: break
        messages.append({"role": "user", "content": input})
```
(abridged)

- The model picks each next step by asking for a tool
- `if not input: break`: no tool request means the model is done

<!-- Call, run any tools it asked for, send the results back, call again. Your code only says "go again while there's something to send back." -->

---

<style scoped>pre, p { font-size: 0.8em; }</style>

# Run the workflow: it rewrites even when it needn't

`uv run lessons/03-control-flow/control_flow.py workflow "write one sentence about agent harnesses in which every word has exactly five letters, at least eight words long"`

```
--- draft ---
Agent tools guide model steps while small loops check every state.

--- review ---
The draft meets every requirement, so nothing needs fixing.
...
--- final ---
Agent tools guide model steps while small loops check every state.
```
(shortened)

<!-- The draft was already right, and the review said so. The rewrite ran anyway, because the code said it would. Predictable, and it does what you laid out even when it isn't needed. -->

---

# Run the agent: it picks its own steps

`uv run lessons/03-control-flow/control_flow.py agent "which folder in lessons has the most files? answer in one English sentence"`

```
$ cd lessons 2>/dev/null && for d in */; do echo "$(find "$d" -type f | wc -l) $d"; done | sort -rn | head -5
10 02-input-and-output/
9 03-control-flow/
7 04-context/
7 01-model-interface/

The `02-input-and-output` folder in `lessons` has the most files, with 10.
```

<!-- Two calls. The first asked for a command; nobody told it which. Its result went back, and the second call answered and asked for nothing, so the loop ended. I didn't plan those steps. The model did. -->

---

# quark.py: the agent loop, plus a chat mode

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

<!-- quark is an agent, so its loop is agent() with Lesson 2's pieces around it. Everything above the control flow section is Lesson 2's, with one addition to input: chat. The growing messages list is how a result reaches the next call. Deciding what really goes in it is Lesson 4. -->

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

# Other things we could do

- **Its shape:** single call, chat, workflow, agent loop, agents handing off, a loop woken by a message or a schedule
- **When it stops:** model stops asking, step count, spending limit, refusal, a person says stop
- **Who it hands back to:** a person, another program, or no one
- **What runs at once:** one model call, or several

[LangGraph](https://github.com/langchain-ai/langgraph) is a product built around this primitive alone.

<!-- quark runs one agent loop with no limit. In LangGraph you lay out the steps and the paths between them as a graph, and it runs them. -->

---

# Two ways to stop that quark leaves out

- **A step limit:** stop after, say, ten calls, even if the model is still asking
- **A refusal:** if `stop_reason` is `"refusal"`, the model declined; going around again won't help
- Either way, say which way it stopped

"Done", "out of steps" and "declined" look the same from outside if it doesn't.

<!-- A step limit is the simplest guard against a loop that never ends: if the model keeps asking for tools, you still get a bill with an end. When it hits the limit, say so, so whoever reads the output knows the task may not be done. -->

---

# Five workflows come up most

- **Prompt chaining:** a fixed sequence of calls
- **Routing:** one call sorts the input, your code picks the path
- **Parallelization:** calls at the same time, then combined
- **Orchestrator–workers:** one call splits the task, others do the pieces
- **Evaluator–optimizer:** one call produces, another judges, repeat

From Anthropic's [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

<!-- Prompt chaining is our workflow(). The evaluator–optimizer is closest to it: make the review answer PASS when the draft is fine, stop when it does, otherwise rewrite and review again, up to a few rounds. Two things to keep straight when you read it. The augmented LLM isn't control flow: retrieval and memory are context, tools are output. And routing stays control flow even when it picks a cheaper model; a backup model that only steps in when the first is down belongs to the model interface. -->

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

<!-- That includes the growing messages list and the prompts in workflow(): what a request holds is context, not control flow. -->

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
