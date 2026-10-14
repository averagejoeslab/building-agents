## 6. How a Model Learns: Gradient Descent

Built, the model is untrained. Its parameters are random, and it writes noise. Training fills them in. This chapter is the one piece of mathematics the book needs, because every later stage (pre-training, mid-training, instruction-tuning, reinforcement learning) is this one idea with different data and different weights on it.

### The training loop

```
loop:
    inputs, targets ← a batch of text, and the same text shifted one token on
    scores          ← model(inputs)                  -- forward pass
    loss            ← how badly scores predict targets
    gradients       ← ∂loss/∂θ for every parameter θ  -- backward pass
    θ               ← θ − learning_rate × step(gradients)
```

In code, one step of it is two lines, from `model/train.py`:

```python
loss = F.cross_entropy(model(inputs).flatten(0, 1), targets.flatten())   # how wrong was it?
optimizer.zero_grad(); loss.backward(); optimizer.step()                # nudge every parameter
```

The rest of the chapter takes those lines apart.

### The targets: the same text, one token on

A language model's training data needs no labels beyond the text. If the text is tokens `[t₁, t₂, t₃, t₄]`, then the inputs are `[t₁, t₂, t₃]` and the targets are `[t₂, t₃, t₄]`: at every position, the right answer is the next token.

```python
starts  = torch.randint(len(data) - 257, (16,))              # 16 random places in the text
inputs  = torch.stack([data[i:i + 256]     for i in starts])  # 256 tokens each
targets = torch.stack([data[i + 1:i + 257] for i in starts])  # the same, one token on
```

Because of the causal mask (Chapter 5), position *i*'s score depends only on tokens up to *i*, so all 256 positions are legitimate predictions, made in one forward pass. A batch of 16 × 256 gives 4,096 predictions per step.

### The loss: cross-entropy

For each position, the model gives a probability to every token in the vocabulary. The loss at that position is the negative log of the probability it gave to the *right* token:

```
loss_i = −log p(target_i)
```

Averaged over every position in the batch, that's the **cross-entropy** loss. Some values to calibrate on:

| Probability given to the right token | Loss |
|---|---|
| 1.0 (certain, and right) | 0.00 |
| 0.5 | 0.69 |
| 0.1 | 2.30 |
| 1/2,048 (a random guess from our small vocabulary) | 7.62 |
| 1/151,936 (a random guess from Qwen's vocabulary) | 11.93 |

So when Chapter 7 reports a held-out loss of 7.69 before training and 5.28 after, you can read it: before, the model did slightly worse than a uniform guess over 2,048 tokens; after, it gave the right token about e⁻⁵·²⁸ ≈ 0.5% probability on average, about ten times better than chance. (The average of log-probabilities is dominated by the hard positions, so "0.5% on average" understates how often it's confidently right.)

The logarithm is used for three reasons. It turns a product of probabilities (the probability of a whole sequence) into a sum, which is numerically stable. It punishes confident mistakes: giving 0.001 to the right answer costs 6.9, not 0.999. And its gradient is simple, as shown below.

In PyTorch, `F.cross_entropy(scores, targets)` applies the softmax to the scores and takes the negative log of the target's probability, in one numerically careful operation. `flatten(0, 1)` merges the batch and position dimensions so every prediction is one row.

### The gradient

The loss is a function of every parameter in the model: change any weight, and the scores change, so the loss changes. The **gradient** of the loss with respect to a parameter is how much the loss would change per unit change in that parameter, right now. A positive gradient means increasing the parameter increases the loss, so we should decrease it.

Computing 600 million gradients is practical because of the **chain rule**. The model is a chain of simple operations (matrix multiplies, additions, softmaxes), each of which has a known derivative. `loss.backward()` walks the chain from the loss back to the inputs, multiplying local derivatives as it goes, and leaves each parameter's gradient in `parameter.grad`. This is **backpropagation**, and it costs about twice a forward pass.

At the output head, the gradient is simple. For one position, with the model's probability vector *p* and the target as a one-hot vector *y*, the gradient of the cross-entropy with respect to the scores is:

```
∂loss/∂scores = p − y
```

The right token's score is pushed up by (1 − p_target), and every wrong token's score is pushed down by its own probability. A wrong token the model was sure about gets pushed hardest. Everything upstream of the output head receives that signal, transformed by the chain rule.

### The step

The simplest update is **gradient descent**: move every parameter a small distance against its gradient.

```
θ ← θ − η · ∂loss/∂θ
```

η is the **learning rate**. Too large, and each step overshoots, so the loss jumps around or diverges. Too small, and training takes too long. The learning rates in this book:

| Stage | Learning rate | Why |
|---|---|---|
| Pre-training, from random | 1 × 10⁻³ | Random weights are far from good ones; big steps are safe |
| Mid-training, instruction-tuning | 1 × 10⁻⁵ | The weights are already good; small steps preserve what they know |
| Reinforcement learning | 1 × 10⁻⁶ | The model trains on its own words; a bigger step broke it (Chapter 18) |

Because the batch is a random sample of the text, each gradient is a noisy estimate of the true one. That's **stochastic** gradient descent. The noise helps: it lets training escape flat regions.

### AdamW: a better step

Plain gradient descent uses the same learning rate for every parameter. But gradients vary widely in scale across a model: an embedding row for a rare token gets a gradient only when that token appears; a weight in every block gets one every step. **Adam** keeps, for each parameter, a running average of its gradient (*momentum*, which smooths the noise) and of its squared gradient (which measures the scale), and divides the step by the scale, so each parameter moves at a sensible rate. **AdamW** adds *weight decay*, a small pull toward zero that keeps weights from growing large.

```python
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)        # pre-training
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.0)   # fine-tuning stages
```

Adam's state is two extra numbers per parameter, so with the gradients, training holds about four numbers for every weight. Every stage in this book uses AdamW.

### A worked step, by hand

Here is a toy example with three tokens, A, B, C, and a "model" that's just three scores, one per token, with no input at all. The training text is `A B A A C`, so the target distribution is A 60%, B 20%, C 20%.

Start with scores *s* = (0, 0, 0). Softmax gives *p* = (⅓, ⅓, ⅓).

Take the batch to be the whole text. The average gradient at the scores is *p* − *ȳ*, where *ȳ* is the average target one-hot, (0.6, 0.2, 0.2):

```
∂loss/∂s = (0.333, 0.333, 0.333) − (0.6, 0.2, 0.2) = (−0.267, 0.133, 0.133)
```

With learning rate η = 1:

```
s ← s − η · ∂loss/∂s = (0.267, −0.133, −0.133)
p = softmax(s)       = (0.428, 0.286, 0.286)
```

A's probability rose from 0.333 to 0.428; B's and C's fell. The loss fell from 1.099 to about 1.012. Repeat, and *p* approaches (0.6, 0.2, 0.2), where the gradient is zero and the loss is as low as it can go for this text. A real model does the same thing, except that its scores depend on the input through 600 million parameters, and the chain rule carries the (*p* − *y*) signal back to all of them.

### Memory tricks the code uses

Training a 600-million-parameter model on one computer's CPU needs three economies, all in `model.py`:

- **Gradient checkpointing.** The backward pass needs every block's intermediate activations. Storing them all for a 1,024-token sequence through 28 blocks is expensive. `torch.utils.checkpoint` keeps only each block's input and recomputes the rest during the backward pass: a third more compute for a large saving in memory.
- **Scoring only what's learned.** The output head is the biggest tensor in the model: 151,936 scores per position. During instruction-tuning, only the assistant's tokens are learned (Chapter 9), so the `keep` mask drops every other position *before* the output head.
- **Saving in bfloat16.** Checkpoints are stored as 16-bit floats, halving the file size. Training itself runs in 32-bit.

### Held-out data

A model can get good at the text it trains on by memorizing it. What we want is for it to get good at text it has never seen.

So before training, some data is set aside, **held out**, and never trained on. After training, we measure the loss on it. If the held-out loss fell, the model learned something general. If only the training loss fell, it memorized. The gap between the two is **overfitting**, and it's why instruction-tuning in Chapter 9 makes exactly one pass over its data: a second pass made the held-out loss rise.

Every stage in this book is checked this way: before and after, on held-out data of its own, asking one question: *did it learn what this stage was meant to teach?*

### The stages

Training happens in stages, because turning random numbers into a useful model has several different goals along the way. Each stage has its own goal, its own data, and its own idea of what counts as right:

| Stage | Goal | Data | Loss is computed on |
|---|---|---|---|
| **Pre-training** | Know language and the world | Everything: the web, books, code; trillions of tokens | Every token |
| **Mid-training** | Be good at what matters for the job | Chosen: maths, code, reasoning, the job's field | Every token |
| **Instruction-tuning** | Behave usefully | Example conversations | The assistant's tokens only |
| **Reinforcement learning** | Succeed reliably | Its own attempts, graded | The assistant's tokens, weighted by the grade |

The split is a convention; labs draw the lines in different places. Pre-training and mid-training put knowledge in. Post-training shapes how the model uses it. Each stage builds on the one before.

### How a model is asked, before it's taught to answer

A model that's only been pre-trained, a **base model**, doesn't answer questions. It continues text. Ask it a question, and it might write three more questions, because that's what often follows a question on the web. So a base model is tested the way labs test one: **by example**. Show it a few examples of the pattern you want, then the start of one more, and let it continue. If it continues the pattern correctly, it knows the answer. Chapter 8's shell check works this way.

The next three chapters go through the stages, one at a time.
