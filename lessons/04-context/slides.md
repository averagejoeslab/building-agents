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

### A hands-on course in building agents by building their harness
Lesson 4

<!-- Lesson 3 gave us an agent. Today we decide what it sees, and that's where almost everything people build into harnesses lives. -->

---

# Every call starts from nothing

The model knows nothing about this moment except what's in the request:

- where it's running, or what day it is
- who it is
- what it did a minute ago
- what you told it last week

<!-- Unless the harness puts it there, the model doesn't know it. And Lesson 3's messages list grows every pass until the model can't read it all. -->

---

# Context decides what the request holds

```
person or world ─► input ─► context ─► request ─► model interface ─► response ─► output ─► person or world
                     ▲                                                              │
                     └─────────────────────────── result ───────────────────────────┘
```

- **Assembles:** chooses what goes in the request, and how it's presented
- **Fits:** when it's bigger than the context window, something has to give

<!-- Input gathers what goes in; context decides what the request actually holds and how it's laid out. It does both jobs before every call. -->

---

# Almost everything is a context component

- **Instructions** and **self-knowledge:** who the model is, how it works
- **Memory:** working, episodic, semantic, procedural
- **Retrieval:** search a store, put what you found in the request
- **Compaction:** when working memory won't fit, summarize some of it

You need the ones your agent needs, built in whatever way fits.

<!-- Almost everything is a way of deciding what the model sees. You don't need all of them. -->

---

# quark.py: Lesson 3, plus a context section

- 234 lines: 86 of code, and a system prompt of 148
- `messages` is renamed `working_memory`; `append` becomes `add()`
- The call is wrapped in `try`, to catch "prompt is too long"
- The new section, context, has eight components

<!-- Everything outside the context section is Lesson 3's, with those two changes in the loop. quark's own version also lets you interrupt it with ESC and retries the summary if the network fails; those are hardening, so they're left out here. -->

---

<style scoped>
table { font-size: 0.8em; }
</style>

# Four memories: the harness records, the model distills

| Memory | Who writes it | Where | How the model sees it |
|---|---|---|---|
| Working | the harness, `add()` | `working_memory` | every call, as the messages |
| Episodic | the harness, `add()` | `.quark/episodes/<start>.jsonl` | by searching, when the past matters |
| Semantic | the model, with bash | `.quark/memory/memory.md` | by reading, when facts matter |
| Procedural | the model, with bash; indexed by `skills()` | `.quark/skills/<name>.md` | the index every call; a skill when it applies |

<!-- Working memory is everything in this session, sent in full on every call. The harness writes what happened; the model writes what it distills from it. -->

---

# The harness writes every message twice

```python
EPISODE = f".quark/episodes/{datetime.datetime.now():%Y-%m-%dT%H-%M-%S}.jsonl"

def remember(message):
    os.makedirs(os.path.dirname(EPISODE), exist_ok=True)
    with open(EPISODE, "a") as f: f.write(json.dumps(message, ...) + "\n")

def add(working_memory, message):
    working_memory.append(message); remember(message)
```

(abridged: comments dropped, one long argument cut to `...`)

<!-- Every message goes into working memory and onto one line of the session's episode file, exactly as it was. An episode is what working memory would have been if nothing had ever been dropped. The model's output is written before any tool runs, so a session that dies mid-command still shows what was asked. The model never writes episodes; it only reads them. -->

---

# The system prompt is rebuilt every call

```
# Self Model
# Memory
## Semantic memory — facts that last
## Procedural memory — how to do things
## Episodic memory — what happened
## Across memories
# World Model
# Other Selves Model
# Body Operations
# Mechanics
```

- Rebuilt each call: the directory, the date and the skill index stay current
- The date but not the time, so the cached prompt stays identical
- `mechanics()` adds quark's own file, with `system()` redacted

<!-- It's written as models of what quark needs to know. cache_control asks the API to cache the prompt, and a cache only hits when the prompt is identical. Mechanics is self-knowledge: the model can see the harness it runs in. -->

---

# Semantic memory is a recipe in the prompt, not code

```
Format (preserve exactly; one fact per line, never two joined with ";" or "and"):
- <subject>: <fact, phrased with the words future-you will grep for>

Write (the quoted heredoc keeps the fact literal):
cat >> .quark/memory/memory.md << 'EOF'
- <subject>: <fact>
EOF
```

- **Distill:** the general truth behind what happened, not a record of it
- No time on a fact: when it was learned is episodic

<!-- This is one excerpt from the prompt. Every store gets the same parts: the store, how to initialize it, the format, the exact write command, what's worth writing, the read moves, and its rules. The read moves are moves, not a menu: quark composes whatever text tools answer the question. -->

---

# Procedural memory: skills, indexed every call

```python
def skills():
    index = []
    for path in sorted(glob.glob(".quark/skills/*.md")):
        ...
    return "\n".join(index) or "- (none yet)"
```

(abridged)

- One Markdown file per skill, with a `name` and `description` at the top
- **Generalize:** the method behind a task, with placeholders, named for the class of task
- The index goes in the prompt; a whole skill is read only when a task matches

<!-- quark writes skills with the exact command in the prompt. skills() is harness code: it reads each skill's header and builds the index, so the model sees what it knows how to do. -->

---

# Recall goes from most distilled to most complete

- **The ladder:** semantic, then procedural, then episodic
- Stop as soon as you have what you need
- Search all three stores at once
- Follow a fact to its skill, and a skill to the sessions that used it
- Find where a fact came from in the episodes: the only store with time

<!-- These are the cross-store moves the prompt gives. Episodic is at the bottom because it's the most complete and the most expensive to read. -->

---

# Compaction is lazy

```python
while True:
    try:
        if drop:
            working_memory, drop = compact(working_memory, drop), 0
        output = call(max_tokens=16384, system=system(), ...).content
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
        continue
```

(abridged)

- The API says "prompt is too long": `drop` goes up by one
- `compact()` drops the oldest `drop` turns and summarizes the rest
- The summary says where the originals are: the episode file

<!-- quark never spends a call on a summary it didn't need, and it loses nothing, because every original is still in the episode file. If even the summary request is too long, drop goes up and it tries again with less. You're unlikely to see it: this model can read about a million tokens. -->

---

# It knows what it is because it's in context

`uv run lessons/04-context/quark.py "what are you, and how do you work? three sentences"`

> I'm quark, an agent that runs on a language model and acts only through bash. It's my one tool for reading, writing, running programs and talking to you. I work in a loop of observe, think, act, and repeat. My working memory is this session's context window. Three stores on disk persist beyond it: semantic facts in `.quark/memory/memory.md`, skills in `.quark/skills/`, and a log of every past session in `.quark/episodes/`.

<!-- Its name, its body, its loop and its memories are all in its context. -->

---

# Facts outlast the session

`"remember that I prefer short answers"` → it appends `- user: prefers short answers`

A new run, `"what do you know about me?"` (shortened):

```
# Quark Memory
- user: prefers short answers
...
Not much:

- You prefer short answers. This is the only fact in my memory.
...
I don't know your name, your work, or anything else about you.
```

<!-- That first run ended. The new one starts with empty working memory. Semantic memory carried the fact, and episodic memory carried what happened: it also told me what I'd asked in earlier sessions. Working memory carried nothing between the runs. -->

---

# It writes a skill for the whole class of task

`"I'll often ask you how many lines of Python are in a repo, not counting .venv. Do it for this one now."`

It answers, then saves this to `.quark/skills/count-python-lines.md` (shortened):

```
---
name: count-python-lines
description: count how many lines of Python are in a repo, excluding .venv (and .git)
---
1. cd to the repo root (default: the current working directory).
...
3. Optionally count files: same find piped to wc -l.
4. Report total lines and number of files.
```

<!-- It answered, 1,949 lines across 24 files, and it wrote two memories: this skill, named for the class of task and not for this repo, and a fact about me that points to the skill. -->

---

# The next session reads the skill first

`"how many lines of Python are in this repo?"` (shortened)

```
$ cat .quark/skills/count-python-lines.md 2>/dev/null
---
name: count-python-lines
...
1949
24
```

> The repo has **1,949 lines of Python** across **24 files**. I excluded `.venv` and `.git` from the count.

<!-- The skill was in the index in its prompt, so the first thing it did was read it and follow it. -->

---

# Only episodic memory knows what you asked

`"what have I asked you in earlier sessions?"` (shortened)

```
In earlier sessions you asked me:

1. "what are you, and how do you work? three sentences"
2. "remember that I prefer short answers"
3. "what do you know about me?"
...
5. "how many lines of Python are in this repo?"
```

<!-- It used the move the prompt gives it: the first line of every episode is the input that opened that session, so one grep lists them all, leaving out the session it's in. -->

---

# Context can be built many ways

- **Who decides what's remembered:** the model, or harness code
- **What it retrieves:** nothing, or documents, code, past messages
- **When it fits:** after the API refuses, or before, by counting tokens
- **How it fits:** summarize old turns, drop them, or cut long tool results
- **How it's laid out:** one prompt, or instructions loaded when needed

Memory layers like [Mem0](https://github.com/mem0ai/mem0) are this primitive alone.

<!-- quark's choices are one set. Mem0 stores what an agent should remember and hands back what's relevant for each request. -->

---

# context.py makes the other choices

- `fit()` counts tokens before every call and summarizes past `LIMIT`
- `trim()` keeps the start and end of a long tool result
- One shared episode log, `.quark/episodes.jsonl`; skills listed by first line

With `LIMIT` set to 560 tokens, after three summaries (shortened):

```
> [working memory over 560 tokens: summarized 3 messages]
Your favorite color is green, going by what you told me earlier in this session.
```

<!-- Counting costs a call each time, and it keeps every request smaller and cheaper than the model's limit. In this chat I told it my favorite color first; fit() summarized before each of the last three inputs, and the fact survived in the summary. -->

---

# The rule: assemble what the request holds, and fit it

- Instructions, self-knowledge, memory, retrieval and compaction all do that
- Who writes each memory is a choice
- The harness writes what happened; the model writes what it distills

<!-- Before every call, context assembles what the request holds and fits it in the space the model has. -->

---

# What context never does

- Get the request to the model and the response back: **model interface**
- Decide when to call, and whether a result goes back around: **control flow**
- Gather what goes in: **input**
- Handle the response: **output**

Context only decides what the request holds and how it fits.

---

# You've built a harness. Now take one apart.

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the request hold? which memories? how does it fit?
├── model interface   where does the request go, and how does the response come back?
└── output            where do outputs go? which tools, and how are they run?
```

- Start with [nanoagent](https://github.com/averagejoeslab/nanoagent), or pick a big one
- Ask what each piece does until it fits one of the five

<!-- Five primitives in 234 lines, and an agent that works, remembers facts, learns skills, recalls what happened, and knows what it is. quark is one set of choices. Is it deciding what the model sees? Then it's context, whatever it's called. If you find something that genuinely fits none of the five, I'd like to hear about it. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Next: Sandboxing

Lesson 5

<!-- That's the primitives. When you're ready to run your harness unattended, the production layers start here. -->
