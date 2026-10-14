## 7. Pre-training: Language and the World

**Goal:** know language, and as much about the world as the text can teach.

Pre-training is the first and by far the largest stage. The model reads an enormous amount of text and learns to predict every next token in it. Nothing else. No questions, no answers, no instructions. Just text, and the next token, everywhere.

It sounds too simple to work. But to predict the next token of a news story well, the model has to pick up grammar, facts about the world, how arguments go, and what people tend to say next. Pre-training is where nearly all of a model's knowledge comes from.

### Our own, from nothing

We pre-train our model from random numbers. It's the same code as the last chapter's, made smaller to fit one computer: 4 blocks instead of 28. Its text is about a million characters of Shakespeare's plays, and its tokenizer learns 2,048 tokens from that same text. The last tenth of the plays is held out.

Before training, its held-out loss is **7.69**, and asked to continue `ROMEO:`, it writes:

> GR9Clengeracices marry confAh condThey villainoud might weep…

After training, its held-out loss is **5.28**, and it writes:

> Two of thy Romeoful days is smoak
> To choose anointed jewry till now,
> Sent both of them, and you shall publace;

Noise has become the shape of a play: verse, line breaks, speakers, real names, near sense. Nobody told it what a play looks like. It learned that from predicting the next token, over and over.

### What a single builder can't afford

The same code, trained by a lab, writes far better. The difference is scale. Qwen's models were pre-trained on about 36 trillion tokens, for months, on a large cluster of specialized computers. That's over 100 million times more text than our Shakespeare.

This is the one stage a single builder can't match. So, as the labs' own open releases allow, we borrow one that's been done: **Qwen3-0.6B-Base**, Qwen's model after its pre-training and mid-training, and before any post-training. Because our code is built to Qwen3's design, its trained numbers load straight in, and its tokenizer's learned merges load into our tokenizer: about 150,000 tokens, the same ones Qwen uses.

Asked to continue the same `ROMEO:`, it writes:

> ROMEO:
> I am Romeo, a man of the world, a man of the city, a man of the law, a man of the law, a man of the law, …

Fluent, then stuck in a loop. It knows language, and a great deal about the world. Nothing has taught it how to behave: when to stop, what's being asked, how to take a turn.

That's what a base model is: a vast store of knowledge with no manners. The next two stages shape it. First, toward the job.
