# repo_template

The structure of the README: building an agent from scratch, end to end. The harness comes first, built around a capable
model, with an evaluation; then the model, built and trained, scored in that harness after every stage.

```
Building agents
│
├─ Intro
│    ├─ What an agent is: a model run inside a harness, its two primitives   [TABLE]
│    ├─ The harness wraps the model; the model outputs one token at a time
│    │    (the model's loop inside the harness's loop)   [DIAGRAM]
│    ├─ Agent = Harness(Model); neither works alone: engine and vehicle
│    ├─ This repo: both built from scratch, then the model trained inside the harness
│    ├─ What the harness needs from the model: four things   [LIST]
│    ├─ Training gets it there one layer at a time: each stage, what it gives the agent   [TABLE]
│    └─ The path: harness around a capable model (Sonnet), with an evaluation
│         → our model, built and trained, scored in that harness after every stage;
│         where compute runs out, a stronger model, said so (Sonnet for the harness; Qwen's numbers)
│
├─ The harness
│    ├─ What it does: output tokens → actions → results back into tokens
│    ├─ Its primitives: shared by every harness   [TABLE] [DIAGRAM]
│    ├─ Building them around Sonnet: each in one line, then its code, then its run, on one job
│    │    model interface · input · output · control flow · context → quark.py
│    ├─ Try it: it works, but changes files unasked, forgets, can hang, records nothing
│    └─ Making it production-ready
│         ├─ Six concerns against the five primitives   [TABLE]
│         ├─ Each concern: how it makes the primitives' implementation production-ready,
│         │    and what addressing it changes for the other concerns   [CODE + RUN]
│         │    persistence · safety · observability · resilience · performance
│         ├─ Evaluation: tasks.py, 32 tasks in four kinds, checked by what was done;
│         │    evaluation only, never trained on   [CODE] [RESULT: Sonnet]
│         └─ → quark_production.py; its model is Sonnet: now we build our own
│
├─ The model
│    ├─ What it does: tokens in, the next token out, appended, repeated   [DIAGRAM]
│    ├─ Its primitives: shared by every model of this kind; we build Qwen3's   [TABLE]
│    ├─ How they predict the next token, together   [DIAGRAM]
│    ├─ Building them: each in one line, then its code
│    │    tokenizer · embedding · position · attention · block · output head · generation
│    └─ Training it: one idea, three stages; each stage scored in quark on tasks.py
│         ├─ Pre-training: ours on Shakespeare, own tokenizer   [DATA] [BEFORE/AFTER]
│         │    → the compute gap → Qwen3-0.6B-Base loaded into our code, every part checked   [CODE] [RESULT]
│         ├─ Our model in quark: one primitive changes, the model interface   [CODE] [RESULT: Base]
│         ├─ Mid-training: shell pages   [DATA] [RESULT]
│         ├─ Post-training
│         │    ├─ Instruction-tuning: six kinds, industry sets and verified sessions from
│         │    │    training tasks kept apart from tasks.py; decontaminated   [DATA] [RESULT]
│         │    └─ RL in the harness: tries at training tasks, graded by their checks;
│         │         the same update, weighted   [CODE] [RESULT]
│         └─ Stage by stage: the same harness and tasks, only the model changes   [TABLE]
│
├─ What we showed, and what we couldn't: a frontier lab's stages beside ours   [TABLE]
│
└─ Run it: the harness, then the model, scored after each stage   [COMMANDS]
```
