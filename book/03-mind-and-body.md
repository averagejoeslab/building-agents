## 3. Mind and Body

Every language agent being built today, however complicated, is made of two parts.

The **model** is the mind. It does one thing: it takes text in and outputs the next piece of text. That's all. It decides, in the sense that what it writes is its choice of what to say or do next. But it can't see anything it isn't handed, it can't remember anything between one use and the next, and nothing it writes happens in the world. It can write the words of a command, and the command doesn't run.

The **harness** is the body. It's everything around the model: it takes in what's happening, gathers what the model needs to see, hands it over, carries out what the model decides, and sends the results back around. It turns the model's words into actions, and what happened back into words.

> **Agent = Harness(Model)**

Neither works alone. A model without a harness is an engine on a workbench: it turns, but goes nowhere. A harness without a model is a car with no engine: everything is in place, and nothing decides where to go.

### What researchers call it

In 2023, researchers from Princeton published a paper called [*Cognitive Architectures for Language Agents*](https://arxiv.org/abs/2309.02427), or **CoALA** (Sumers, Yao, Narasimhan and Griffiths). It noticed that people building language agents were reinventing, one project at a time, ideas cognitive science had worked out decades earlier, and it gave them a common map. A language agent, in CoALA's terms, has:

- **Memory:** a *working memory* for what's in mind now, and long-term memories that are *episodic* (what happened), *semantic* (what's true, about the world and itself) and *procedural* (how to do things). Procedural memory lives in two places: in the model's trained numbers, and in the agent's own code.
- **Actions:** *external* ones, which reach into the world, like running a command or talking to a person; and *internal* ones, which work on its own memory: *retrieving* (bringing something from long-term memory into working memory), *reasoning* (thinking in working memory) and *learning* (writing to long-term memory).
- **A decision cycle:** a loop in which it proposes what it might do, weighs the options, picks one, and carries it out, then observes what happened and goes again.

This book uses the same map. The model is the reasoning. The harness provides everything else: the working memory, assembled fresh each time; the long-term memories, kept on disk; the actions; and the cycle.

### The five parts of every harness

Harnesses go by many names: framework, scaffold, runtime, orchestration layer. The industry has mostly settled on *harness*. However it's built, every harness has the same five jobs:

| Part | What it does | In cognitive science |
|---|---|---|
| **Input** | Takes in what comes from outside: a request, or the result of an action | Perceiving |
| **Context** | Assembles what the model needs to see: instructions, the conversation, memories | Working and long-term memory |
| **Model interface** | Sends that to the model, and brings back its response | The link between deciding and the rest |
| **Output** | Handles the response: shows its words, or carries it out as an action | Acting |
| **Control flow** | Decides what happens next: go again, hand back, or stop | The cycle |

Text comes in, is gathered with what the model needs, goes to the model, and the model's response is carried out. Whatever the action returns comes back in as input, and the cycle repeats. Inside the model, a smaller loop runs too: it writes one piece of text at a time, adding each to what it reads before writing the next.

### How the labs build agents

The labs that make the most capable agents build both parts themselves, in this order:

1. **They build the model,** designing its architecture.
2. **They pre-train it,** on trillions of words of text, so it learns language and how the world works.
3. **They mid-train it,** on chosen material, so it gets good at what matters for its job, such as code or reasoning.
4. **They post-train it,** so it behaves usefully: taking turns in a conversation, following requests, stopping when it's done.
5. **They build the harness** the agent will live in.
6. **They train the model in its harness,** with examples of the agent at work and with practice, so the mind learns to use the body it actually has.
7. **They check every stage,** on material it never trained on, and evaluate the finished agent, in its harness, on held-out tasks of the kind it will do.

Then they ship the model and the harness together, and whatever the evaluations found becomes the plan for the next round.

This book follows those steps, in that order. Part II builds and trains the mind. Part III builds the body. Part IV puts the mind in the body and trains it there.
