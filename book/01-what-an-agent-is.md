# Part I: The Agent

## 1. What an Agent Is

Imagine waking up in a dark room you've never seen. You don't know where you are or how you got there. What do you do?

You listen. You reach out and feel for a wall. You think: *a wall, so I'll follow it.* You take a step. You feel again, think again, step again. Each thing you learn changes what you do next, and each thing you do teaches you something new.

That's the loop every agent runs. In cognitive science, the study of how minds work, an **agent** is a system that perceives its surroundings, keeps what it needs in memory, decides, and acts, in a cycle:

- **Perceive:** take in what's happening.
- **Decide:** work out what to do about it.
- **Act:** do it. Choosing to do nothing is an action too.

Then **perceive again**, because acting changes the world, and the change is the next thing to take in.

You're an agent. So is a thermostat, in a very small way: it perceives the temperature, decides it's too cold, and turns on the heat. A chess program is one, and so is a robot vacuum. A thing is an agent when it runs this loop, however simple it is.

### The loop, as a program

Everything in this book is built on one shape. Written as pseudocode, an agent is:

```
state ← initial memory
loop:
    observation ← perceive(world)
    state       ← remember(state, observation)
    action      ← decide(state)
    world       ← act(world, action)
    if action is STOP: break
```

Each of the four verbs becomes a real piece of software by the end of Part III. `decide` will be a language model. `perceive`, `remember` and `act` will be the harness. The loop itself will be a few lines of control flow. When something later in the book seems complicated, find which of these four verbs it belongs to.

### Memory

The loop needs memory, because deciding well depends on more than what's in front of you right now. Cognitive science describes several kinds, and we'll build all of them:

| Kind | What it holds | In you | In our agent (Chapter 14) |
|---|---|---|---|
| **Working memory** | What's in mind right now | The sentence you're reading | The model's context window |
| **Episodic memory** | What happened | What you did this morning | A log of every session, on disk |
| **Semantic memory** | What's true | That Paris is the capital of France | A file of facts, one per line |
| **Procedural memory** | How to do things | How to ride a bike | The model's weights, and a folder of skills |

Working memory is small, fast, and rebuilt constantly. The other three are long-term: they last, and you reach into them when you need something.

### Language agents

For most of computing history, agents were narrow. A thermostat decides only about heat. A chess program only plays chess. Each one's `decide` was written by hand, rule by rule, for its one job.

What changed is the arrival of **language models**: programs that read and write text well enough to reason about almost anything that can be described in words. A language model can be the `decide` of an agent, for almost any job. Give it a description of the situation, and it writes what to do next.

An agent built that way is a **language agent**, or an **LLM agent**, after the *large language model* at its center. This book builds one from nothing.

A language model alone is not an agent. It can decide, but it can't perceive, remember, or act. Chapter 3 covers the rest.
