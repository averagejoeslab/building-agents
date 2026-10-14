# Appendix B: Glossary

Each term is defined where it's first used; this is the list in one place, with the chapter.

| Term | Meaning | Ch |
|---|---|---|
| **Advantage** | A try's reward minus the group's average, often divided by the group's spread: how much better than usual it did | 18 |
| **Agent** | Anything that loops over perceiving, deciding and acting | 1 |
| **AdamW** | The optimizer used at every stage: a gradient step scaled per parameter by running averages of its gradient and squared gradient, with weight decay | 6 |
| **Attention** | The part of a block where each token compares its query with earlier tokens' keys and takes a weighted share of their values | 5 |
| **Backpropagation** | Computing every parameter's gradient by the chain rule, from the loss back through the model | 6 |
| **Base model** | A model after pre-training (and mid-training), before post-training: it continues text but doesn't take turns | 6, 7 |
| **Baseline** | A value subtracted from each reward to reduce the noise of the policy gradient; here, the group's average | 18 |
| **Block** | Attention plus a small network, each with a residual connection; stacked to make the model | 5 |
| **BPE (byte-pair encoding)** | The tokenizer's learning algorithm: start from bytes, repeatedly merge the commonest neighbouring pair | 5 |
| **Causal mask** | The rule that a token can only attend to tokens before it, which makes the model a next-token predictor | 5 |
| **Chat template** | The fixed pattern of special tokens that lays a conversation out as text; it ships with the model | 9 |
| **CoALA** | *Cognitive Architectures for Language Agents* (Sumers, Yao, Narasimhan, Griffiths, 2023): a map of language agents in terms of memory, actions and a decision cycle | 3 |
| **Context** | Everything the model is shown on one call: system prompt, tools, conversation. The harness part that assembles it | 13 |
| **Context window** | The most tokens a model can read at once | 4 |
| **Control flow** | The harness part that decides what happens next: go again, hand back, or stop | 12 |
| **Cross-entropy** | The loss: the negative log of the probability the model gave to the right next token, averaged | 6 |
| **Curriculum** | A choice of training tasks that keeps them at a difficulty the model passes some of the time | 20 |
| **Decontamination** | Removing training data that resembles the evaluation; here, by word overlap of 40% or more | 8, 17 |
| **Embedding** | The vector a token is turned into: a row of the embedding table | 5 |
| **Episodic memory** | Memory of what happened; here, every message of every session, on disk | 1, 14 |
| **Evaluation** | Tasks with known right answers, never trained on, checked by what the agent did | 15 |
| **Gradient** | How much the loss would change per unit change in a parameter | 6 |
| **Greedy decoding** | Always picking the most likely token (temperature 0) | 4 |
| **GRPO** | Group relative policy optimization: policy gradient with the group's own average reward as the baseline | 18 |
| **Harness** | Everything around the model that lets it perceive, remember and act | 3, 10 |
| **Held-out data** | Data set aside and never trained on, to measure whether learning generalizes | 6 |
| **Input** | The harness part that captures what comes in: a person's request, or a tool's result | 11 |
| **Instruction-tuning** | Post-training on example conversations, learning the assistant's tokens only | 9, 17 |
| **KL penalty** | A loss term for how far the model's probabilities have moved from a frozen reference copy | 18 |
| **Learning rate** | The size of each gradient step | 6 |
| **Logits** | The model's raw scores for every token, before softmax | 4 |
| **Loss** | A number measuring how wrong the model's predictions were; training makes it smaller | 6 |
| **Mid-training** | Next-token prediction on data chosen for the job | 8 |
| **Model** | The part of an agent that decides: tokens in, next token out | 3, 4 |
| **Model interface** | The harness part that sends the context to the model and brings back its response | 11, 16 |
| **Output** | The harness part that handles the response: shows words, carries out tool calls | 11 |
| **Output head** | The last step of the model: compares the final vector with every token's embedding to score it | 5 |
| **Overfitting** | Getting better on training data while not improving (or worsening) on held-out data | 6, 7 |
| **Policy** | In RL, the model seen as a probability distribution over replies | 18 |
| **Policy gradient** | The gradient of expected reward: the average, over sampled tries, of reward times the gradient of the try's log-probability | 18 |
| **Post-training** | Training that shapes behaviour: instruction-tuning, then reinforcement learning | 9 |
| **PPO** | Proximal policy optimization: a policy-gradient method that clips how far each step can move the policy | 18 |
| **Pre-training** | Next-token prediction on as much text as possible | 7 |
| **Procedural memory** | Memory of how to do things; in the model's weights, and here in a folder of skills | 1, 14 |
| **Reinforcement learning (RL)** | Training from graded tries rather than given examples | 18 |
| **Residual connection** | Adding a part's output to its input rather than replacing it, so signal passes through many blocks | 5 |
| **Reward** | The grade of a try; here, 1 if the task's check passes, 0 if not | 18 |
| **RMSNorm** | Rescaling a vector to a steady size; used before attention and the network in each block | 5 |
| **RoPE (rotary position embedding)** | Marking position by rotating queries and keys by an angle that grows along the text | 5 |
| **Self model** | Instructions written from the agent's own point of view: who it is, its body, its memories | 13 |
| **Semantic memory** | Memory of what's true; here, a file of facts, one per line | 1, 14 |
| **Softmax** | Turning scores into probabilities: exponentiate each, divide by the total | 4 |
| **System prompt** | The instructions at the start of the context, which the model was trained to weigh most | 13 |
| **Temperature** | Dividing scores before softmax to sharpen (below 1) or flatten (above 1) the distribution | 4 |
| **Token** | A piece of text, as an integer; what a model reads and writes | 4 |
| **Tool** | A capability described to the model, which it asks to use with a structured call | 11 |
| **Top-k, top-p** | Sampling only from the *k* likeliest tokens, or from the likeliest whose probabilities sum to *p* | 4, 5 |
| **Trajectory** | One try at a task, as a sequence of replies and results | 18 |
| **Transformer** | The model architecture of this book: embedding, a stack of attention-and-network blocks, an output head | 5 |
| **Working memory** | What's in mind now; for a language agent, the context window | 1, 13 |
