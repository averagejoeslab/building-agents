# repo_template

The structure of the README: building an agent from scratch, end to end, in the order you'd build it.
Each section mirrors the other: what it does, its primitives, building them, making it useful, what you have.

```
Building agents
│
├─ Intro
│    ├─ Building an agent from scratch = building two things: a model and a harness
│    ├─ How the two make an agent (table: model · harness, what each does)
│    ├─ The harness wraps the model: captures input, assembles context,
│    │    requests a response, acts on the output, decides what happens next
│    ├─ Agent = Harness(Model)
│    ├─ Neither works alone: the model is the engine, the harness the rest of the vehicle
│    ├─ Each is itself built from primitives
│    └─ The path, stated up front:
│         we build everything ourselves; where compute runs out, we swap in a stronger model.
│         Our model pre-trains small → Qwen loads in for mid- and post-training
│         → Sonnet drives the harness while we build it → our model trains in the harness.
│
├─ The model
│    ├─ What it does: tokens in, the next token out, appended, repeated   [DIAGRAM]
│    │    TokensOut = Model(TokensIn)
│    ├─ Its primitives: shared by every model of this kind; we build Qwen3's   [TABLE]
│    ├─ How they predict the next token, together   [DIAGRAM]
│    ├─ Building them: each in one line, then its code
│    │    tokenizer · embedding · position · attention · block · output head · generation
│    │    → built, but it knows nothing
│    ├─ Training it
│    │    ├─ The one idea: measure the surprise, nudge every number   [CODE]
│    │    ├─ Pre / mid / post: a convention; each with its own goal, data and idea of right   [TABLE]
│    │    ├─ Pre-training: know language and the world
│    │    │    ├─ Our model, small, on Shakespeare, with our own tokenizer   [DATA] [BEFORE/AFTER]
│    │    │    └─ The compute gap → load Qwen3-0.6B-Base into our code:
│    │    │         its numbers into our model, its merges into our tokenizer;
│    │    │         load every part, check it   [CODE] [BEFORE/AFTER]
│    │    ├─ Mid-training: be good at what matters (shell pages)   [DATA] [BEFORE/AFTER]
│    │    └─ Post-training: behave usefully
│    │         ├─ Instruction-tuning: four kinds of conversation   [DATA] [BEFORE/AFTER]
│    │         └─ RL: a try is a task done in its harness → after the harness   [CODE]
│    └─ What we have: it outputs tool-call tokens, and nothing happens   [EXAMPLE]
│         → it needs a harness, and a real agent needs a far stronger model:
│           the same compute gap, so the harness is built with Sonnet,
│           then our model goes into it and trains there
│
├─ The harness
│    ├─ What it does: turns output tokens into actions, and results back into tokens
│    │    Agent = Harness(Model)
│    ├─ Its primitives: shared by every harness   [TABLE] [DIAGRAM]
│    ├─ Building them: each in one line, then its code, then its run, on one job
│    │    model interface · input · output · control flow · context
│    │    → with a model in it, it's an agent: quark.py
│    ├─ Try it: it works, but changes files unasked, forgets, can hang, records nothing
│    └─ Making it production-ready
│         ├─ Six concerns against the five primitives   [TABLE]
│         ├─ Each concern: how it makes the primitives' implementation production-ready,
│         │    and what addressing it changes for the other concerns   [CODE + RUN]
│         │    persistence · safety · observability · resilience · performance · evaluation
│         └─ → quark_production.py: a production-ready agent, built from scratch
│
├─ Training the model in its harness: post-training, part two
│    ├─ Our model in quark: one primitive changes, the model interface   [RESULT]
│    ├─ RL in the harness: tries graded by tasks.py's checks, the same update   [BEFORE/AFTER]
│    │    → the same harness with Qwen3-0.6B and with Sonnet
│    └─ What we showed, and what we couldn't: a frontier lab's stages beside ours   [TABLE]
│
└─ Run it: each stage in order   [COMMANDS]
```
