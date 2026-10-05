# harness-engineering

**A hands-on course in building agents by building their harness.**

## What is harness engineering?

I'm not going to give you a definition. People are bad at saying what they mean and good at showing it, and I'm no exception. I've seen it at conferences: talk after talk, people use different words for the same thing — framework, scaffold, runtime, orchestration layer — while the thing itself is still evolving. The words don't line up, but when they show you how it works, it's the same thing every time. A definition only says what something is; a mechanism shows it.

So instead of saying what I mean, I'll show you: what an agent is made of, and what each part does.

An agent works by two mechanistic primitives:

- **The model** predicts. Given tokens, it produces the tokens most likely to come next: **TokensOut = Model(TokensIn)**.
- **The harness** does everything else. It decides how inputs are gathered, how they're presented to the model, how it interfaces with the model, how the model's outputs are handled, and how information flows between all of them.

> **Agent = Harness(Model)**

The model goes inside; the harness wraps it. Harness engineering is the work of building that second primitive.

The first primitive is built by **model development**: training data, compute, and the methods to train and evaluate a model. If you want to know how a model works inside, read [the model deep dive](./docs/the-model.md). It's optional. This repo is about the harness.

## What is a harness made of?

Five mechanistic primitives. Control flow is one of them, and the other four sit inside it:

```
control flow          how information flows between the other four: run once, a chat loop, an agent loop, a workflow
├── input             how inputs are gathered, from a person or the world
├── context           how those inputs are presented to the model
├── model interface   how the harness interfaces with the model
└── output            how the model's outputs are handled: shown to a person, or run as tools
```

Anything you build around a model that does these five things is a harness. How you build each one is up to you. Control flow shows this most clearly: run the other four once and you have a single call. Loop and hand back after every reply and you have a chatbot. Keep looping while the model asks to use tools and you have an agent. Claude Code, Cursor, Codex, and the harness you'll build here are all these five primitives with different choices made.

Input and output are built independently, but they're two ends of the same exchange, so this repo teaches them together.

## How this repo teaches

You've just watched the method. Take a thing and ask, *what is it, and by what mechanistic primitives does it work?* An agent is a model and a harness. A harness is control flow, input, context, model interface and output. Ask once more and the answers stop being shared: one harness reads a terminal, another a Slack channel. That's where taking apart ends.

The lessons go the other way and build it back up, one primitive at a time. The example throughout is [quark](https://github.com/averagejoeslab/quark), my own agent in 81 lines of Python. It's one way to build each primitive, not the only way. Each lesson stands on its own: it tells you what the primitive is, why a harness needs it and how it works, shows quark's version as code, has you run that code, then recaps with what else would have worked.

| # | Lesson | You build |
|---|---|---|
| 1 | [Model interface](./lessons/01-model-interface/) | how the harness interfaces with the model: one call, and its reply |
| 2 | [Input and output](./lessons/02-input-and-output/) | how inputs are gathered, and how outputs are handled: shown to a person or run as a tool |
| 3 | [Control flow](./lessons/03-control-flow/) | how information flows: the loop that sends a result back and goes again |
| 4 | [Context](./lessons/04-context/) | how inputs are presented to the model: who it is, what's happened, what it remembers |

By the end of Lesson 4 you've built quark, and you can take apart any harness someone hands you.

## Setup

macOS or Linux · Python 3.13+ · [uv](https://docs.astral.sh/uv/) · an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

> [!WARNING]
> From Lesson 2 on, the agent runs shell commands the model writes, with no confirmation. Run it somewhere you can afford to lose.

**→ [Start with Lesson 1](./lessons/01-model-interface/)**

## License

MIT.
