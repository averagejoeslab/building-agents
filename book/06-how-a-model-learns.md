## 6. How a Model Learns

Built, the model is untrained. Its millions of numbers are random, and it writes nonsense. Training fills them in.

Training is one idea, repeated billions of times:

1. **Show it real text.** Take some text, and at every position, ask the model to predict the token that actually comes next.
2. **Measure how surprised it was.** If it gave the real next token a high score, it wasn't surprised. If it gave it a low score, it was. This surprise, averaged over every position, is the **loss**. Lower is better.
3. **Nudge every number.** Work out, for each of the millions of numbers, which way to move it to make the model a little less surprised. Move each a little.

Then do it again, on more text. Each nudge is tiny. Billions of them add up to a model that predicts real text well, and to predict real text well, it has to pick up grammar, facts, reasoning, and style along the way.

### Held-out data

A model can get good at the text it trains on by memorizing it. That isn't what we want. We want it to get good at text it has never seen.

So before training, some data is set aside, **held out**, and never trained on. After training, we measure the model on that held-out data. If it does better there, it learned something general. If it does better only on what it trained on, it memorized.

Every stage of training in this book is checked this way: before and after, on held-out data of its own, asking one question: **did it learn what this stage was meant to teach?**

### The stages

Training happens in stages, because turning random numbers into a useful model has several different goals along the way. Each stage has its own goal, its own data, and its own idea of what counts as right.

| Stage | Goal | Data | What counts as right |
|---|---|---|---|
| **Pre-training** | Know language and the world | Everything: the web, books, code; trillions of tokens | The next token, everywhere |
| **Mid-training** | Be good at what matters for the job | Chosen: maths, code, reasoning, the job's field | The next token, everywhere |
| **Post-training** | Behave usefully | Example conversations; then its own attempts, graded | The answer's tokens; then whatever earns reward |

The split is a convention, not a law. Labs draw the lines in different places. But the shape is the same everywhere: pre-training and mid-training put knowledge in; post-training shapes how the model uses it. Post-training can't add much knowledge. It teaches behavior, and the model becomes whatever the grading rewards. Each stage needs the one before it.

### How a model is asked, before it's taught to answer

There's a catch in checking an early model. A model that's only been pre-trained, a **base model**, doesn't answer questions. It continues text. Ask it a question, and it might write three more questions, because that's what often follows a question on the web.

So a base model is asked the way labs ask one: **by example.** You show it a few examples of the pattern you want, then the start of one more, and let it continue. If it continues the pattern correctly, it knows the answer.

The next three chapters go through the stages, one at a time.
