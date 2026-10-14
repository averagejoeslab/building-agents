# Building Agents

### From nothing to a model, a harness, and a model trained in its harness

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

---

## Preface

This book is about how an agent is built from scratch: not by calling someone else's AI, but by making each part yourself. You'll build the model, the mind that decides, and train it. You'll build the harness, the body that lets the mind see and act. Then you'll train the mind inside its body, so it gets better at using it.

That's how the labs that make frontier agents work. They build a model, train it in stages, build the harness the agent will live in, and then train the model inside that harness. This book follows the same path at the scale of one computer. Where one computer runs out, we say so, and borrow something bigger.

Everything in it really happened. Every number, every quote from a model, every success and failure comes from a real run, kept in the [`building-agents`](https://github.com/averagejoeslab/building-agents) repository alongside the code. You don't need to read the code to follow the book. Each chapter explains what was built, why, and what happened, in plain words. If you want to see how, the code is there.

The book follows one agent, **quark**, from nothing to working, and one small job, from the first chapter where it appears to the last:

> A tiny project works out the price of a shopping basket. One of its tests is failing: it's supposed to take ten percent off, and it doesn't. The request is always the same: *"The tests are failing. Find out why and fix it."*

Watch how much has to exist before anything can do that on its own.

---

## Contents

**Part I: The Agent**

1. [What an Agent Is](./01-what-an-agent-is.md)
2. [Why Build One](./02-why-build-one.md)
3. [Mind and Body](./03-mind-and-body.md)

**Part II: Building the Mind**

4. [What a Model Does](./04-what-a-model-does.md)
5. [The Seven Parts of a Model](./05-the-seven-parts-of-a-model.md)
6. [How a Model Learns](./06-how-a-model-learns.md)
7. [Pre-training: Language and the World](./07-pre-training.md)
8. [Mid-training: Knowing the Job](./08-mid-training.md)
9. [Post-training: Learning to Behave](./09-post-training.md)

**Part III: Building the Body**

10. [What a Harness Is](./10-what-a-harness-is.md)
11. [Reach, Ask, Act](./11-reach-ask-act.md)
12. [Closing the Loop](./12-closing-the-loop.md)
13. [Context: What It Knows](./13-context.md)
14. [Ready to Leave Running](./14-ready-to-leave-running.md)
15. [Knowing It Works](./15-knowing-it-works.md)

**Part IV: Training the Mind in Its Body**

16. [The Mind Moves In](./16-the-mind-moves-in.md)
17. [Learning from Examples](./17-learning-from-examples.md)
18. [Learning from Its Own Tries](./18-learning-from-its-own-tries.md)
19. [Reading the Results](./19-reading-the-results.md)
20. [The Next Round](./20-the-next-round.md)

**Part V: The Method**

21. [Building an Agent from Scratch](./21-building-an-agent-from-scratch.md)
