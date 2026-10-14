## 9. Post-training: Learning to Behave

**Goal:** turn a model that continues text into one that takes turns, answers what it's asked, and stops.

A base model is like someone who has read everything and never had a conversation. Post-training teaches it to have one. It comes in two kinds, and an agent needs both:

- **Instruction-tuning** teaches by example. The model is shown conversations, and learns to write the way the assistant in them does.
- **Reinforcement learning** teaches by practice. The model tries things, its tries are graded, and it learns to do more of what earned a good grade.

This chapter covers what post-training is, and what instruction-tuning teaches a model about talking. Its most important work for an agent, learning to act in a harness, and all of reinforcement learning, need the harness to exist. They come in Part IV.

### The chat template

To take turns, a model has to know whose turn it is. So a conversation is laid out in a fixed pattern of special tokens that mark where each turn starts, who is speaking, and where each turn ends: the **chat template**. For the model we train, a turn looks like this:

> `<|im_start|>user`
> `How do I make a cup of tea?<|im_end|>`
> `<|im_start|>assistant`
> `To make a cup of tea, …<|im_end|>`

The model reads the whole conversation in this pattern. When the harness wants a reply, it lays out the conversation and ends with the start of the assistant's turn. The model writes from there, and when it writes the end-of-turn token, it's done.

We post-train in the chat format of Qwen's own post-trained model, so that ours speaks the same format as the model we'll later compare it with.

### Learning from the assistant's words only

Instruction-tuning is still next-token prediction, with one change: the model only learns from the **assistant's** tokens. It reads the user's words, but isn't graded on predicting them. It's being taught to be the assistant, not the user.

Our instruction-tuning data mixes six kinds of conversation, 2,400 in all. Five are public, chosen to teach broad habits, 300 of each:

| Kind | What it teaches |
|---|---|
| Talk | Everyday conversation |
| Ask for a command | Turning a request into a shell command |
| Reason | Working through a problem step by step, in a thinking block, before answering |
| Call tools | The format for asking to use a tool |
| Write code | Writing programs from a description |

The sixth kind, 900 recordings of our agent at work in its harness, is the most important for an agent, and Chapter 17 is about it. All six were trained together, in one pass: a second pass starts memorizing. Every number in the model is trained, including the embeddings, because the base model has barely learned the token that ends a turn.

### Before and after

On 48 held-out conversations, the loss drops from **2.260** to **0.496**. More telling is what it writes.

Asked *"How do I make a cup of tea?"*, before:

> ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ ⚙ …

After:

> To make a cup of tea, follow these steps:
> 1. Gather your materials: You will need a teapot, a cup, a teabag, and a pot of water.
> 2. Boil the water: …

Asked a word problem (*Carmen has $100, Samantha has $25 more than Carmen, and Daisy has $50 more than Samantha; how much do all three have?*), before, it writes a different word problem. After, it thinks first, then answers:

> *Samantha has $25 + $100 = $125. Daisy has $50 + $125 = $175. All three girls have $125 + $175 = $200 combined.* The answer is 200.

It now takes turns, answers what was asked, and stops. It has the *shape* of reasoning, but not yet the substance: it left Carmen out, and the right answer is 400. Instruction-tuning teaches behavior. It can't give a 600-million-number model arithmetic it doesn't have.

We have a mind that can hold a conversation. It still can't do anything. Now we build its body.
