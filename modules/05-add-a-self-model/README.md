# Add a self model

> **Harness component: the system prompt.** The harness decides what the model knows about itself, its surroundings, and the people it's working with — before it reads a single message. In quark, that's a structured self model, rebuilt on every call.

The Module 4 agent has a body but no idea what it is. It doesn't know it's an agent, where it's running, what day it is, or how to use bash well. All of that is context the harness can supply — and supplying it is where *the model handles what it can* starts paying off. This module adds no new mechanism to the loop. It adds a `system()` function, and one argument to the stream call.

## The checkpoint

[`examples/05_self_model.py`](../../examples/05_self_model.py) is Module 4 plus two changes:

```python
def system(): return f"# Self Model\n\n**Identity:** You are quark — ..."   # one long f-string (shown rendered below)
```

```python
    with client.messages.stream(model=MODEL, max_tokens=4096, system=system(), tools=body, messages=working_memory) as stream:
```

(and `datetime` joins the imports). `system()` is a **function**, called fresh on every model call, because parts of the prompt are live: the working directory and the current time.

## The prompt, rendered

This is what the model reads at the top of every call:

```markdown
# Self Model

**Identity:** You are quark — a self in a world with other selves.
**Mind:** your context window — where thinking happens.
**Body:** bash — your singular means of acting and observing. Its reach is the whole system: anything doable from a command line — any program, any language, any tool you install — is within it.
**Loop:** observe → think → act → repeat.

# World Model

**Environment:** terminal — what surrounds you.
**Where:** /Users/you/project
**When:** 2026-10-01 13:30:42

# Other Selves Model

**Other selves:** entities in the environment with their own self-models — humans, other agents. They reach you via text input. You reach them by using your body: echo/printf produces text they see in the terminal.

# Body Operations

One bash invocation per response (prefer focused actions to keep results small).
When utils fall short, escalate: compose pipes → inline interpreters (python -c) → write and run scripts → install tools. Prefer the lightest act that does the job.

Acts:
- on world: file ops, programs, system commands
- on other selves: echo/printf

Observes:
- of world: ls, cat, ps, env, date, pwd, etc.

Before acting, derive what the observation really means — the intent behind a message, the signal within a result. Then ground from the nearest source outward, pivoting only when one comes up empty: mind (already in context) → world → asking other selves.
```

## Three models and a body

The prompt is organized as three models — the same three any agent, human or otherwise, needs to get around:

- **Self Model** — what quark *is*. Its **mind** is the context window: where thinking happens, and (as Module 6 will add) finite. Its **body** is bash, and the prompt deliberately describes its reach as *the whole system* — without that line, models tend to anchor on basic coreutils and treat `python -c` or installing a tool as an exotic workaround, even though they know how. The **loop** names the cycle the harness runs: observe → think → act.
- **World Model** — where it is. The environment (a terminal), the working directory, and the time. The model has no other way to know these; the harness hands them over.
- **Other Selves Model** — who it's working with. The humans (or other agents) who reach it with text, and how it reaches them.

## Body Operations: teaching, not tooling

The last section is the know-how a toolkit would otherwise encode in code:

- **One bash invocation per response, focused.** Small, deliberate acts keep results small, which keeps the mind from filling with noise.
- **An escalation gradient.** Pipes first, then an inline interpreter, then a script, then installing a tool — "prefer the lightest act that does the job." This licenses escalation without inviting a `pip install` for every question.
- **Acts and observes, by target.** Acting on the world (files, programs) versus acting on other selves (speaking). Observing the world (`ls`, `cat`, `date`). Module 7 adds a third target: the self.
- **A grounding gradient.** Before acting, work out what an observation really means — the intent behind a message, the signal within a result — then look for the answer from the nearest source outward: what's already in context, then the world, then ask the human. This came from watching quark in live sessions: asked for its user's name, it ran `finger` against the system for an answer it had already been given. One sentence in the prompt fixed a behavior no amount of code could. (The full story involves memory, which slots into this gradient in Module 7.)

None of this is enforced. It's taught. That's the trade quark makes everywhere: a sentence in the prompt is cheaper, more flexible, and easier to change than a function in the harness — and the model is good at following it.

## One vocabulary

Notice that the prompt and the code now speak the same language. The prompt says *mind*; the code's conversation list is `working_memory`. The prompt says *body*; the tool list is `body`. The prompt says acts *reach the world*; the harness's placeholder from Module 4 says *your doing … never reached the world*. When the model reads a harness message, it's in the vocabulary it was taught. Module 9 takes this to its conclusion, when the model reads the code itself.

Speaking deserves one note. quark's text output streams to your terminal like any chatbot's, and the prompt also frames `echo`/`printf` as a way to speak — bash output is printed to the human, so writing to the terminal through the body *is* talking. The model uses both; the framing just keeps "speaking" inside the one-body picture.

## Run it

```bash
cd examples
uv run 05_self_model.py
```

Ask it who it is, where it is, or what time it is. Then ask it something that needs a tool it doesn't have installed, and watch it climb the escalation gradient.

## What's missing

- **Its mind fills up.** Every turn adds to `working_memory`. Eventually the conversation exceeds the context window, the API returns `400 prompt is too long`, and the program crashes.
- **It forgets everything when it exits.**
- **You still can't stop it mid-act.**

Module 6 handles the full mind.

---

**Next:** [Module 6: Add working memory](../06-add-working-memory/)
