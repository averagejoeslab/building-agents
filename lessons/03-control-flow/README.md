# Lesson 3: Control flow

> 🎥 **Video:** coming soon

Control flow is how information flows between the other four primitives. They all sit inside it: it decides what runs, in what order, and whether to go again.

Here's the path one pass takes, with the pieces from Lessons 1 and 2:

```
person or world ─► input ─► request ─► model interface ─► response ─► output ─► person or world
                     ▲                                                   │
                     └───────────────────── result ──────────────────────┘
```

Input gathers what goes into the request. The model interface sends it and gets the response back. Output handles the response: it shows it to a person, or runs a tool. A tool's result is input again. Control flow decides what happens at the end of the path: the result goes back around, a person gets a turn, or everything stops.

How you arrange them decides what you've built:

- **Run once.** Input, call, output, stop. That's Lesson 2.
- **A chat loop.** Call, show the response, hand back to the person, repeat. A chatbot.
- **A workflow.** Your code decides the steps: call the model to draft, then to check, then to fix.
- **An agent loop.** Call, and while the model asks for tools, run them, send the results back, and call again. Hand back when it stops asking.

There's no correct one. They differ in who decides what happens next: in a workflow, your code does; in an agent, the model does. A workflow is predictable and easy to test, but only handles what you planned for. An agent handles what you didn't plan for, and costs you predictability.

Whatever the shape, control flow does two things. It **sequences** the other primitives, passing what one produced to the next. And it **terminates**: it decides when to stop, or when to hand back to a person. A loop with no clear way to end is a bill with no clear way to end.

## The concept

Here's the idea with nothing around it: who decides the next step. The same file runs it both ways, in [`control_flow.py`](./control_flow.py):

```python
import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def call(messages, **request):
    return client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, messages=messages, **request).content

def ask(prompt):
    return "".join(block.text for block in call([{"role": "user", "content": prompt}]) if block.type == "text")

def workflow(input):                                     # your code decides the next step: draft, review, rewrite, stop
    draft = ask(f"Do this task. Reply with only the result.\n\n{input}")
    print(f"--- draft ---\n{draft}\n")
    review = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nCheck the draft against every requirement in the task. List what to fix, or say it's fine.")
    print(f"--- review ---\n{review}\n")
    output = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nReview:\n{review}\n\nRewrite the draft to fix everything in the review. Reply with only the new draft.")
    print(f"--- final ---\n{output}")

def agent(input):                                        # the model decides the next step: ask for a tool, or stop
    messages = [{"role": "user", "content": input}]
    while True:
        output = call(messages, tools=tools)
        messages.append({"role": "assistant", "content": output})
        input = []
        for block in output:
            if block.type == "text": print(block.text)
            if block.type == "tool_use":
                print(f"$ {block.input['cmd']}")
                done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                print(done.stdout)
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
        if not input: break                              # no tool request: the model is done
        messages.append({"role": "user", "content": input})

mode, input = sys.argv[1], " ".join(sys.argv[2:])
workflow(input) if mode == "workflow" else agent(input)
```

`call()` and `ask()` are the model interface, cut down to one line each. The two functions below them are the two answers to who decides.

**`workflow()`** is your code deciding. It calls the model three times, always in the same order: draft, review, rewrite. Then it stops. The model writes every word, but it never chooses what happens next. There are no tools, and nothing the model says can add a step or skip one.

**`agent()`** is the model deciding. It calls the model, runs any tools it asked for, sends the results back, and calls again. The model chooses each next step by asking for a tool, and it chooses when to stop by not asking. Your code only says "go again while there's something to send back."

Run both from the root of the repo:

```bash
uv run lessons/03-control-flow/control_flow.py workflow "write one sentence about agent harnesses in which every word has exactly five letters, at least eight words long"
uv run lessons/03-control-flow/control_flow.py agent "which folder in lessons has the most files? answer in one English sentence"
```

Here's the workflow:

```
--- draft ---
Agent tools guide model steps while small loops check every state.

--- review ---
The draft meets every requirement, so nothing needs fixing.

- **One sentence:** It is a single sentence with one closing period.
- **Length:** It has 11 words, which clears the minimum of eight.
- **Five letters per word:** Agent, tools, guide, model, steps, while, small, loops, check, every and state each have exactly five letters.
- **Topic:** It describes what an agent harness does, with tooling that guides the model's steps and loops that check state. The word "harness" has seven letters, so it can't appear. The sentence conveys the idea without it.

--- final ---
Agent tools guide model steps while small loops check every state.
```

The draft was already right, and the review said so. The rewrite ran anyway, because the code said it would. That's a workflow: predictable, and it does what you laid out even when it isn't needed.

Here's the agent:

```
$ cd lessons 2>/dev/null && for d in */; do echo "$(find "$d" -type f | wc -l) $d"; done | sort -rn | head -5
10 02-input-and-output/
9 03-control-flow/
7 04-context/
7 01-model-interface/

The `02-input-and-output` folder in `lessons` has the most files, with 10.
```

Two calls. The first asked for a command; nobody told it which. Its result went back, and the second call answered and asked for nothing, so the loop ended. I didn't plan those steps. The model did.

## quark's implementation

quark is an agent, so its loop is `agent()` with Lesson 2's pieces around it: streaming, the one tool, and `read()` for a person. It adds one thing the concept doesn't have, a chat mode, so the loop can hand back to you instead of ending. Here's the whole of [`quark.py`](./quark.py):

```python
import subprocess, sys
from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(each=lambda event: None, **request):            # model interface: the response streams back, and each piece goes to each()
    with client.messages.stream(model=MODEL, **request) as stream:
        for event in stream: each(event)
        return stream.get_final_message()

# ── output: the one tool ────────────────────────────────────────────────────
tools = [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def show(event):                                         # output: text, shown as it's written
    if event.type == "text": print(event.text, end="", flush=True)
    if event.type == "content_block_stop" and event.content_block.type == "text": print()

# ── input ───────────────────────────────────────────────────────────────────
def read(prompt):                                        # input: from a person
    while True:
        print(prompt, end="", flush=True)
        line = sys.stdin.readline()
        if not line: return "/q"                         # end of input (Ctrl-D): nothing more is coming
        if line.strip(): return line.rstrip("\n")        # Enter on an empty line: a fresh prompt, as in a terminal
        prompt = "> "
input = " ".join(sys.argv[1:]) or read("> ")
if input == "/q": sys.exit()
chat = len(sys.argv) < 2

# ── control flow ────────────────────────────────────────────────────────────
messages = [{"role": "user", "content": input}]

while True:
    output = call(show, max_tokens=16384, tools=tools, messages=messages).content
    messages.append({"role": "assistant", "content": output})

    input = []
    for block in output:                                 # output: run tool requests
        if block.type == "tool_use":
            print(f"$ {block.input['cmd']}")
            done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            print(done.stdout)
            input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})  # input: from the world

    if input:
        messages.append({"role": "user", "content": input})
        continue
    if not chat or (input := read("\n> ")) == "/q":
        break
    messages.append({"role": "user", "content": input})
```

Everything above `# ── control flow ──` is Lesson 2's, with one addition to input: **`chat`**, which is true when nothing came in on the command line. The new section is the loop.

**`while True:`** means go again. Each pass is one call to the model.

**`messages`** is how a result reaches the next call. The first entry is the input that started the run. Right after each call, the model's `output` is appended; if the model asked for tools, the `input` they produced is appended after it. Each request carries everything so far. That growing list is the simplest form of context, working memory. Deciding what really goes in it is Lesson 4.

**`if input: ... continue`** is the agent loop. If the model asked for anything, what came back goes in and the loop calls again.

**No input from the world** is termination. The model decides it's done by not asking for a tool. quark doesn't count steps or look for a magic word.

**`chat`** gives one loop two modes. With input on the command line, quark runs until the model stops asking for tools, then exits. With none, it's a chat: when the model's turn ends, it hands back to you with `> `, `read()` gathers your next input, and `/q` (or Ctrl-D) quits.

Notice what the loop doesn't have: a step limit. quark trusts the model to finish. That's a choice, and if the model never stops asking, quark never stops.

### Run it

From the root of the repo:

```bash
uv run lessons/03-control-flow/quark.py "which quark.py in the lessons folder is the longest? answer in one sentence"
```

Here's one run:

```
$ find . -path "*lessons*" -name "quark.py" -exec wc -l {} + | sort -n | tail -5
   12 ./lessons/01-model-interface/quark.py
   38 ./lessons/02-input-and-output/quark.py
   51 ./lessons/03-control-flow/quark.py
  239 ./lessons/04-context/quark.py
  340 total

The longest one is `./lessons/04-context/quark.py`, at 239 lines.
```

That's two calls. The first asked for a command. Its result went back, and the second call answered from what it found. Run it with no input to chat with it instead.

## Other things we could do

quark runs one agent loop with no limit, but this primitive holds more in other harnesses.
- **Its shape.** A single call, a chat loop, a workflow, an agent loop, agents that hand tasks to other agents, a loop that wakes on a message or a schedule.
- **When it stops.** When the model stops asking, after a number of steps, at a spending limit, when the model declines, when a person says stop.
- **Who it hands back to.** A person, another program, or no one: it runs until the task is done.
- **What runs at the same time.** One model call at a time, or several at once.

It can be a product on its own. [LangGraph](https://github.com/langchain-ai/langgraph) is built around this primitive: you lay out the steps and the paths between them as a graph, and it runs them.

Two ways to stop that quark leaves out are worth knowing.

- **A step limit.** Count the calls, and stop after, say, ten, even if the model is still asking. It's the simplest guard against a loop that never ends: if the model keeps asking for tools, you still get a bill with an end. When it hits the limit, say so, so whoever reads the output knows the task may not be done.
- **Stopping when the model declines.** The API tells you why a response ended in `stop_reason`. If it's `"refusal"`, the model has declined, and going around again won't help. Stop, and say that's why.

A loop that stops in more than one way should always say which way it stopped. "Done", "out of steps" and "declined" look the same from outside if it doesn't.

Anthropic's [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) names the workflows that come up most:
- **Prompt chaining.** A fixed sequence of calls, each working on the last one's output, with checks in code between them if you want. That's `workflow()` above.
- **Routing.** One call sorts the input, and your code sends it down the path built for that kind.
- **Parallelization.** Calls run at the same time, either splitting a task into independent parts or asking the same thing several times and combining the answers.
- **Orchestrator–workers.** One call breaks the task into pieces as it goes, other calls do the pieces, and the results are combined.
- **Evaluator–optimizer.** One call produces something, another judges it against the task, and the loop repeats until the judge passes it.

The evaluator–optimizer is the one `workflow()` is closest to. Make the review answer with only `PASS` when the draft is fine, stop when it does, and otherwise rewrite and review again, up to a few rounds. Then the rewrite only runs when it's needed. It's still a workflow: the loop is in your code, and the model only fills in the draft and the verdict.

Two things to keep straight when you read the article. Its building block, the *augmented LLM*, is a model with retrieval, tools and memory, and that isn't control flow: retrieval and memory are context, and tools are output. And routing stays control flow even when the path it picks is a cheaper model: that's a decision about the work, unlike a backup model that only steps in when the first is down, which belongs to the model interface.

## What to take away

**The rule:** control flow sequences the other four primitives and decides when to stop. Arranged differently, the same four pieces are a single call, a chatbot, an agent, or a workflow.

Notice what control flow never does. Getting the request to the model and the response back is the model interface. Gathering what goes in is input, and handling the response is output. What each request holds, including that growing `messages` list and the prompts in `workflow()`, is context. Control flow only decides what runs, in what order, and when to stop.

**What's missing:** this is an agent, but it knows nothing. Not where it is, not what day it is, not who it is, not what you told it yesterday. And `messages` grows every pass; in a long session it will outgrow what the model can read. Something has to decide what the model sees. That's context.

**→ [Lesson 4: Context](../04-context/)**
