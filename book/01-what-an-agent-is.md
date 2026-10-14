# Part I: The Agent

## 1. What an Agent Is

Imagine waking up in a dark room you've never seen. You don't know where you are or how you got there. What do you do?

You listen. You reach out and feel for a wall. You think: *a wall, so I'll follow it.* You take a step. You feel again, think again, step again. Each thing you learn changes what you do next, and each thing you do teaches you something new.

That's the loop every agent runs. In cognitive science, the study of how minds work, an **agent** is a system that perceives its surroundings, keeps what it needs in memory, decides, and acts, in a cycle:

- **Perceive:** take in what's happening.
- **Decide:** work out what to do about it.
- **Act:** do it. Choosing to do nothing is an action too.

Then **perceive again**, because acting changes the world, and the change is the next thing to take in.

You're an agent. So is a thermostat, in a very small way: it perceives the temperature, decides it's too cold, and turns on the heat. A chess program is one, and so is a robot vacuum. What makes something an agent isn't how clever it is. It's the loop.

### Memory

The loop needs memory, because deciding well depends on more than what's in front of you right now. Cognitive science describes several kinds, and we'll use all of them in this book:

| Kind | What it holds | In you |
|---|---|---|
| **Working memory** | What's in mind right now | The sentence you're reading, and what it's about |
| **Episodic memory** | What happened | What you did this morning |
| **Semantic memory** | What's true | That Paris is the capital of France |
| **Procedural memory** | How to do things | How to ride a bike |

Working memory is small and fast and constantly changing. The other three are long-term: they last, and you reach into them when you need something.

### Language agents

For most of computing history, agents were narrow. A thermostat decides only about heat. A chess program only plays chess. Each one's deciding was written by hand, rule by rule, for its one job.

What changed is the arrival of **language models**: programs that read and write text well enough to reason about almost anything that can be described in words. A language model can be the *deciding* part of an agent, for almost any job. Give it a description of the situation, and it can decide what to do next.

An agent built that way is a **language agent**, or an **LLM agent**, after the *large language model* at its center. This book is about building one from nothing.

But a language model alone is not an agent. It can decide, but it can't perceive, remember, or act. Before we see why, it's worth asking why anyone would want to build one at all.
