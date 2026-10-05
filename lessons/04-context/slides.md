---
marp: true
theme: default
paginate: true
header: "Lesson 4 · Context"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Context

### Building agents by building their harness
Lesson 4 of 4

---

# Where we left off

The agent loop works.

But the agent knows nothing.

---

# What the model doesn't know

- where it runs
- today's date
- who it is
- what it did a minute ago
- what you said last week

---

# Every call starts from nothing

The model knows only what is **in the request**.

Unless the harness puts it there.

---

# Context

**How inputs are presented to the model.**

Input gathers. Context decides what the request holds and how it is laid out.

---

# Where it sits

```
person/world → input → CONTEXT → request → model interface
                                                  ↓
          (result loops back to input) ← output ← response
```

---

# Context does two things

Before every call:

1. **Assembles**: what goes in, and how it is presented
2. **Fits**: the request must fit the context window

---

# Fitting: something has to give

The window has a limit.

When the request is bigger, something must be cut.

---

# The components

- Instructions
- Working memory
- Episodic memory
- Semantic memory
- Procedural memory
- Retrieval
- Compaction
- Self-knowledge

You only need the ones your agent needs.

---

# Instructions

The system prompt.

Standing guidance for every call.

---

# Working memory

This session, sent in full each call.

---

# Episodic memory

A record of past sessions.

---

# Semantic memory

Durable facts: who you are, your preferences, past mistakes.

---

# Procedural memory

Recipes, playbooks, skills.

Read when relevant.

---

# Retrieval

Search a store.

Put the results in the request.

---

# Compaction

Summarize when it won't fit.

---

# Self-knowledge

Tell the model what it is and how it works.

---

# Quark's version

`quark.py` is 48 lines.

Lesson 3, plus five components.

---

# Component 1: working memory

Lesson 3's `messages`, **renamed** `working_memory`.

The whole session is sent in full on every call.

---

# Component 2: instructions

```python
reply = client.messages.create(..., system=system(), ...)
```

Passed on every call.

---

# `system()` is a function

So the working directory and date are **current** on every call.

```python
os.getcwd()
datetime.date.today()
```

---

# How the prompt is written

As models of the world:

- **Self Model**: identity, mind, body, loop
- **World Model**: where, when
- **Other Selves Model**: who else exists
- **Body Operations**: how to act

---

# Why the date, not the time

The prompt carries `cache_control: ephemeral`.

A cache hit needs an **identical** prompt.

A timestamp would change it every call.

---

# Component 3: self-knowledge

```python
def mechanics(): ...
```

Quark reads its own file with `__file__`.

It appends it under `# Mechanics` at the end of the system prompt.

---

# A small trick

The `def system():` line is replaced with a placeholder.

Otherwise the prompt would contain itself.

---

# Component 4: semantic memory

`.quark/memory/memory.md`

There is **no memory code**.

---

# Memory lives in the prompt

The system prompt tells the model:

- the file path
- the entry format
- how to write (printf plus heredoc)
- how to read (grep, tail)
- what is worth keeping

Quark uses the bash it already has.

---

# Component 5: compaction

```python
def compact(working_memory, drop): ...
```

When the request won't fit, summarize.

---

# Compaction is reactive

```python
except BadRequestError as e:
    if "prompt is too long" not in str(e): raise
    drop += 1
    continue
```

Wait for the API to refuse, then compact.

---

# How `compact` works

1. Find the plain-text user turns
2. Discard the oldest `drop` turns
3. Ask the model to summarize the rest
4. Return one message: "[your prior working memory, summarized] ..."

---

# If the summary is too long too

`drop` rises and it retries with less.

If it can't get small enough, it exits.

---

# Tradeoff

It never spends a call on an unneeded summary.

The oldest turns are dropped **unsummarized**.

---

# Compaction is the other primitives

The summary is one more call through Lesson 1's interface.

Looping again is Lesson 3.

Only what working memory holds is new.

---

# Rarely seen

The model reads about 1M tokens.

Quark's real version also adds an ESC interrupt and a summary retry on network failure. That is hardening, omitted here.

---

# Run it: self-knowledge

```bash
uv run lessons/04-context/quark.py \
  "what are you, and how do you work? three sentences"
```

It knows its name, body, loop and memory file, from context alone.

---

# Run it: remember

```bash
uv run lessons/04-context/quark.py \
  "remember that I prefer short answers"
```

It writes an entry to `memory.md` using bash.

---

# Run it: recall

New run:

```bash
uv run lessons/04-context/quark.py \
  "what do you know about me?"
```

It reads memory and reports your preference.

---

# What carried over

Working memory **didn't** carry between runs.

Semantic memory **did**.

---

# Going further: who decides what's remembered

- the model
- the harness code, saving and loading automatically

---

# Going further: retrieval and fitting

- **Retrieval**: nothing, or docs, code, past messages by search
- **When** it fits: after the API refuses, or before, by counting tokens
- **How** it fits: summarize old turns, drop them, cut long tool results

---

# Going further: layout

One system prompt.

Or instructions loaded only when the task needs them.

---

# Mem0

A memory layer as a product.

This primitive.

---

# A richer example: `context.py`

56 lines.

No `memory.md`, no `mechanics()`.

Different choices for the same primitive.

---

# Episodic memory: `remember`

```python
def remember(message):
    # append json to .quark/episodes.jsonl
```

`add(working_memory, msg)` appends and remembers.

A record of every message.

---

# Using the episodes

The system prompt tells the model the log exists.

It searches `.quark/episodes.jsonl` when the past matters.

---

# Procedural memory: skills

`.quark/skills/*.md`

The system prompt lists each as `path: first line`, or "(none yet)".

The model reads the one that fits before a covered task.

---

# Skill demo

Skill: "How to count lines of Python in this repo".

The model reads it, follows it, and reports: **327 lines**, largest `input_output.py` at 64.

---

# Recall demo

A later session greps `episodes.jsonl` and recalls 327.

---

# Fitting, how: `trim`

```python
def trim(text):
    # if over KEEP: first half + "[... N characters cut ...]" + last half
```

Applied to each tool result before it enters working memory.

---

# Fitting, when: `fit`

```python
client.messages.count_tokens(...).input_tokens < LIMIT
```

**Proactive**: count before the call, not after a refusal.

---

# What `fit` does when over

1. Keep the last user turn onward
2. Summarize everything before it
3. Print `[working memory over LIMIT tokens: summarized N messages]`

The loop calls `fit` before every `create`.

---

# Fit demo

Set `LIMIT = 560` and chat.

Your favorite color, green, **survives** in the summary.

---

# Mapping the choices

- episodic memory: `add` and `remember`
- procedural memory: skills in `system()`
- when it fits: `fit()` counts tokens
- how it fits: `trim()`

---

# What to take away

**Rule:** before every call, context assembles what the request holds and fits it into the model's space.

Memory, retrieval, instructions and compaction are all ways of doing that.

It never does model interface, control flow, input or output.

---

# You've built a harness

Five primitives, 48 lines.

---

# Next: read other harnesses

Sort the parts of any harness under the five primitives.

- **Control flow**: what loops, who stops it
- **Input**: where it comes from
- **Context**: what the request holds, how it fits
- **Model interface**: where it goes, how it returns
- **Output**: where it goes, which tools

---

# Two rules for sorting

If it decides what the model sees, it's **context**, whatever it's called.

If it acts on the model's words, it's **output**.

---

# Try it on `nanoagent`

github.com/averagejoeslab/nanoagent (TypeScript)

If something fits none of the five, the author wants to hear about it.

---

# After the primitives

Production layers begin at Lesson 5.

---

<!-- _class: title -->

# Thank you

You've built a harness.
