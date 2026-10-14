# Building Agents

### From nothing to a model, a harness, and a model trained in its harness

By **[Chase Dovey](https://cdovey.dev/)** · [Average Joes Lab](https://github.com/averagejoeslab)

---

## Preface

This book builds an agent from scratch, and teaches each step as it goes. Every chapter shows the code it describes, annotated line by line; the diagrams of each architecture; the actual training examples the model learned from; the arithmetic of gradient descent and reinforcement learning, worked by hand; pseudocode for the harness that you can carry to any language; and, in an appendix, step-by-step instructions for reproducing every experiment, with the numbers you should see.

The code is the real code: the [`building-agents`](https://github.com/averagejoeslab/building-agents) repository, which holds a model built from its parts (`model/model.py`, about 350 lines), its training in stages (`model/train.py`, about 800 lines), a harness built one primitive at a time (`harness/`), and the record of every run (`runs/`). Where the book shows a shorter version of a function, to fit the page or to make one idea stand out, it says so, and the full version is in the repository at the path given.

You'll need to read Python to follow the code. You don't need to have trained a model before, or built an agent. The book builds both, in order, and explains each idea the first time it's used.

The book follows one agent, **quark**, from nothing to working, and one small job, from the first chapter where it appears to the last:

> A tiny project works out the price of a shopping basket. One of its tests is failing: it's supposed to take ten percent off, and it doesn't. The request is always the same: *"The tests are failing. Find out why and fix it."*

Watch how much has to exist before anything can do that on its own.

---

## Contents

**[Download the book as a PDF](./Building-Agents.pdf)**

**Part I: The Agent**

1. [What an Agent Is](./01-what-an-agent-is.md)
2. [Why Build One](./02-why-build-one.md)
3. [Mind and Body](./03-mind-and-body.md)

**Part II: Building the Mind**

4. [What a Model Does](./04-what-a-model-does.md)
5. [The Seven Parts of a Model](./05-the-seven-parts-of-a-model.md)
6. [How a Model Learns: Gradient Descent](./06-how-a-model-learns.md)
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
18. [Learning from Its Own Tries: Reinforcement Learning](./18-learning-from-its-own-tries.md)
19. [Reading the Results](./19-reading-the-results.md)
20. [The Next Round](./20-the-next-round.md)

**Part V: The Method**

21. [Building an Agent from Scratch](./21-building-an-agent-from-scratch.md)

**Appendices**

- A. [Reproducing Every Experiment](./A-reproducing-every-experiment.md)
- B. [Glossary](./B-glossary.md)

## License

The book is licensed under [CC BY 4.0](../LICENSE-CC-BY-4.0), and its code under the [MIT License](../LICENSE). Its data sources and fonts keep their own licenses: see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
