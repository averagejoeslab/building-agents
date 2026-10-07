---
marp: true
theme: default
paginate: true
header: "harness-engineering"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# harness-engineering

### A hands-on course in building agents by building their harness
Chase Dovey · Average Joes Lab

<!-- Welcome. This deck introduces the whole course: what a harness is, how the lessons build one, and what's in the repo besides the lessons. Each lesson has its own deck after this one. -->

---

# Three parts

1. **The course.** What a harness is made of, then ten lessons that build one
2. **The paper.** The course's thesis, tested against Claude Code, OpenAI Codex and opencode
3. **quark at work.** The harness you build in Lesson 4 doing real work on this repo

<!-- Read them in this order. The course is where to start. The paper is the argument for people who want it, and quark at work is the proof: the harness from Lesson 4 doing real work on this repo, from its own memory, across ten sessions. -->

---

# No definition

- Framework, scaffold, runtime, orchestration layer: different words, same thing
- People are bad at saying what they mean and good at showing it
- A definition only says what something is; **a mechanism shows it**
- So instead of saying what I mean, I'll show you

<!-- I've seen it at conferences: talk after talk, people use different words for the same thing while the thing itself is still evolving. When they show you how it works, it's the same thing every time. So this course shows what an agent is made of and what each part does. -->

---

# An agent works by two mechanistic primitives

- **The model** predicts: **TokensOut = Model(TokensIn)**
- **The harness** does everything else

## Agent = Harness(Model)

<!-- The model goes inside; the harness wraps it. The harness decides how inputs are gathered, how they're presented to the model, how it interfaces with the model, how the model's outputs are handled, and how information flows between all of them. Harness engineering is the work of building that second primitive. -->

---

# This course is about the harness

- The model is built by **model development**: training data, compute, and the methods to train and evaluate a model
- How a model works inside is an optional deep dive
- The harness is the part you build here

<!-- Model development is its own field. If you want to know what's inside the model, the repo has a deep dive in docs/the-model.md. It's optional. Everything else in this course is about the harness. -->

---

# What is a harness made of?

| Primitive | What it does |
|---|---|
| **control flow** | how information flows between the other four |
| **input** | how inputs are gathered, from a person or the world |
| **context** | what the request holds, and how inputs are presented in it |
| **model interface** | how the harness interfaces with the model |
| **output** | how the model's outputs are handled: shown to a person, or run as tools |

<!-- Five mechanistic primitives. Control flow is one of them, and the other four sit inside it. Anything you build around a model that does these five things is a harness. Input and output are built independently, but they're two ends of the same exchange, so the course teaches them together. -->

---

# Same five primitives, different choices

- Run the other four once: **a single call**
- Loop and hand back after every reply: **a chatbot**
- Keep looping while the model asks to use tools: **an agent**
- Claude Code, Cursor, Codex, and the harness you'll build here are all these five primitives with different choices made

<!-- How you build each primitive is up to you. Control flow shows this most clearly: the same four primitives, run once, looped, or looped while the model uses tools, give you three different things. -->

---

# The method

- Take a thing and ask: *what is it, and by what mechanistic primitives does it work?*
- An agent is a model and a harness
- A harness is control flow, input, context, model interface and output
- Ask once more and the answers stop being shared: one harness reads a terminal, another a Slack channel
- That's where taking apart ends

<!-- You've just watched the method. Keep asking the question until the answers stop being shared between harnesses. That's where the primitives are. -->

---

# Then build it back up

- One primitive at a time, outward from the model
- Lesson 1 calls the model and nothing else
- Lessons 2–4 each add what the last one was missing: input and output, then control flow, then context
- Each one's `quark.py` is the previous lesson's plus that

<!-- The lessons go the other way. Each lesson's deficiency is exactly the next lesson's primitive. That's the argument, and it's the lesson order. -->

---

# quark

- The example throughout is **quark**, my own agent
- One way to build each primitive, not the only way
- Every lesson shows:
  1. its idea on its own, in a small file you can run
  2. what quark adds to it and why, with runs
  3. the other things it could be, in words

<!-- Every lesson follows the same shape. First the concept with nothing around it, then quark's implementation, then what else that primitive or layer could be. -->

---

# The primitives: Lessons 1–4

| # | Lesson | You build |
|---|---|---|
| 1 | Model interface | one call, and its reply as it streams back |
| 2 | Input and output | how inputs are gathered, and how outputs are handled |
| 3 | Control flow | the loop that sends a result back and goes again |
| 4 | Context | who it is, what's happened, what it remembers |

<!-- These four are the part to learn first. Lesson 4's quark.py is the finished harness. By then you've built quark, and you can take apart any harness someone hands you. -->

---

# A harness that works isn't yet one you'd run unattended

- The production layers add **hardening**: safe, watchable, dependable and fast
- None of it is a new primitive
- Each layer folds back into the primitives it's built on, and each lesson shows where
- Each lesson's `quark.py` is the one before it plus that layer, and nothing else

<!-- Lessons 5 to 10 build on the harness you finish Lesson 4 with. They don't add a sixth primitive. Each one says which primitives it's built on. -->

---

# The production layers: Lessons 5–10

| # | Lesson | Built on |
|---|---|---|
| 5 | Sandboxing | output |
| 6 | Guardrails | control flow |
| 7 | Observability | control flow |
| 8 | Resilience | model interface, output |
| 9 | Performance | context, model interface, output, control flow |
| 10 | Evaluation | the whole harness |

<!-- The order is the order you'd want them in. First the box, so the agent can't do lasting damage; then the gate in front of it; then a record of both; then surviving failures, then cost and speed, and last, a way to tell whether any of it still works. -->

---

# Jev: a second model

- From Lesson 5 on, each layer's concept comes twice: on its own, then with one question for **Jev**
- Jev is a small model that makes decisions instead of writing text
- What a command needs from the box, whether it only reads, whether a tool failed, whether a failure will pass, how big a request is, whether the agent finished
- Then quark gets both

<!-- It's a way to see where a second model fits in a harness, and what it can and can't be trusted with. Without a TypeSafe key, quark decides the old way. -->

---

# The paper

## *Agent = Harness(Model): Five Mechanistic Primitives of LLM Agent Harnesses*

- **The claim:** an agent is a model wrapped in a harness, and every harness is made of five primitives
- **Production:** every production concern folds back into those five instead of adding a sixth
- **A test on real harnesses:** Claude Code, OpenAI Codex and opencode, part by part
- **A case study:** the ten runs of quark at work, failures included

<!-- The paper is the course's thesis, written up for people who want the argument rather than the lessons. It also has rules for the hard cases, such as where a tool call's effect lands, backup models versus routing, and who a file is for. It's a preprint. -->

---

# quark at work

The `quark.py` you finish Lesson 4 with, nothing added, doing real work on this repo. In ten sessions, it:

- brought the four primitive lessons' slide decks into line with the lessons
- turned all ten decks into PDFs
- reviewed the paper
- weighed in on the order of the production lessons

<!-- This is the proof. Each session started with empty working memory. Anything it knew beyond the prompt came from its three memory stores: the facts it had written down, the skills it had saved, and the record of every earlier session. So most prompts were kept short on purpose, to make it use them. -->

---

# Memory at work

- *"Now do the same for Lesson N's slides."*
- A new session has no idea what "the same" means
- The skill was in the index in its prompt, so its first command was to read it
- Later it answered questions about its past from its episodes

<!-- Run 2a got a full prompt and saved its method as a skill. Runs 2b, 2c and 2d each got one line, and each found out what "the same" meant from that skill. The last two sessions asked about the past and nothing else, and it answered from the record of every earlier session. -->

---

# What we checked

- We reviewed everything quark changed before it was merged
- Its corrections to the paper were right
- We fixed two unreadable slides by hand
- Its memory slipped: a fact it didn't replace, a note where a skill edit belonged

<!-- Memory is a summary, and a summary can be wrong in ways that read as confident. That's why the review step exists. The README lists everything we checked and everything we fixed by hand. -->

---

# Setup

- macOS or Linux · Python 3.13+ · uv · an Anthropic API key
- Lessons 5–10 also need Docker, and a TypeSafe key for Jev
- Put your keys in `.env` at the root of the repo (it's gitignored)

```bash
cp .env.example .env        # then add your keys to .env
export UV_ENV_FILE=.env
```

<!-- Without a TypeSafe key, quark decides the old way, so the production lessons still run. -->

---

# A warning

From Lesson 2 on, the agent runs shell commands the model writes, with no confirmation.

**Run it somewhere you can afford to lose.**

<!-- Lesson 5 puts its commands in a box and Lesson 6 puts a gate in front of them. Until then, nothing stands between the model and your machine. -->

---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Start with Lesson 1

### Model interface

<!-- We start at the model itself, with the primitive that calls it. -->
