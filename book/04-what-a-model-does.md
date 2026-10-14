# Part II: Building the Mind

## 4. What a Model Does

A language model predicts what comes next.

It doesn't read words the way you do. It reads **tokens**: small pieces of text, each one an integer. A common word is usually one token. A rare word might be several. Spaces and punctuation are parts of tokens too.

Give a model a sequence of tokens, and it produces a score for every token in its vocabulary: how likely that token is to come next. One token is picked, appended, and the model runs again on the longer sequence. Token by token, it writes. It stops when the picked token is a special one that means *the end*.

> **TokensOut = Model(TokensIn)**

That is all a model does.

```
            ┌──────────── append ◄────────────┐
            ▼                                 │
TokensIn ─► Model ─► scores ─► pick one ──────┤
                                              │
                                    is it the end? ── yes ─► TokensOut
```

### One prediction, all the way through

Here is a real model predicting a real next token. The model is **Qwen3-0.6B**, an open model with about 600 million parameters (the numbers inside it), whose design this book builds. The text is *"The capital of France is"*.

```
"The capital of France is"
        │  tokenizer
        ▼
[785, 6722, 315, 9625, 374]                      5 tokens
        │  embedding + position
        ▼
5 × 1,024 numbers                                each token's meaning, and where it is
        │  28 blocks: attention (look back) + network (think about it)
        ▼
5 × 1,024 numbers                                each token, now in context
        │  output head
        ▼
5 × 151,936 scores                               for every possible next token, at every position
        │  generation: take the last position's highest score
        ▼
" Paris"                                         appended to the input, and round again
```

Step by step:

1. **Text becomes tokens.** The tokenizer splits the text into five pieces and looks up each one's number: 785 is `The`, 6722 is ` capital`, 315 is ` of`, 9625 is ` France`, 374 is ` is`. Note the leading spaces: they're part of the token.
2. **Tokens become vectors.** Each token number is a row in a table, and the row is a vector of 1,024 numbers. The vector is the token's *embedding*: what it means, as far as training has worked out. Its position in the sequence is marked too.
3. **Vectors take in their context.** The five vectors pass through 28 *blocks*. In each, every token looks back at the tokens before it, takes in what it needs from them, and is then transformed further. After 28 blocks, each token's vector stands for what it means *here*, in this sentence.
4. **The last position predicts.** The final vector is compared with every token's embedding, all 151,936 of them, giving each a score. (The model actually scores every position, which training uses; for generation only the last one matters.)
5. **One is picked.** The highest score is for ` Paris`. It's appended, and the whole thing runs again to predict what follows.

Asked to keep going, our implementation of this model writes: *"The capital of France is Paris. The capital of Germany is Berlin. The capital of…"* It has learned what tends to follow what.

### Scores, probabilities, and picking

The output head's scores are called **logits**. They're turned into probabilities by the **softmax** function: raise *e* to each score, and divide by the total, so the probabilities sum to 1:

```
p(token_i) = exp(s_i) / Σ_j exp(s_j)
```

The model gives every token a probability. Something else picks. There are several ways to:

| Way | What it does | When it's used |
|---|---|---|
| **Greedy** (temperature 0) | Always the highest probability | Evaluation, so a score repeats exactly |
| **Temperature** | Divide the scores by *T* before softmax. *T* < 1 sharpens the distribution; *T* > 1 flattens it | Generation, to vary output |
| **Top-k** | Keep only the *k* most likely tokens, then sample | To cut off the long tail of unlikely tokens |
| **Top-p** (nucleus) | Keep the most likely tokens whose probabilities sum to *p*, then sample | The same, adapting to how spread out the distribution is |

The code for all four is in Chapter 5, under *Generation*. This is why you can ask a model the same thing twice and get two different answers, and why every evaluation in this book uses temperature 0.

### Why "next token" is enough

Whether predicting the next token amounts to reasoning depends on what it takes to predict well. To predict the next token of *"The capital of France is"*, the model has to know the fact. To predict the next token of a half-finished proof, it has to follow the proof. To predict the next token of a shell session, it has to know what the commands do. Trained on enough text, a model that predicts well has absorbed whatever structure the text contains, because that structure is what makes the next token predictable.

### What a model can't do

A model:

- **can't see.** It knows only the tokens it's given.
- **can't remember.** Every call starts fresh. A conversation only seems remembered because the whole thing is sent again each time.
- **can't act.** It writes tokens. If those tokens spell out a command, nothing runs it.
- **can only take in so much.** There's a limit to how many tokens it can read at once, its **context window**. Qwen3-0.6B's is 32,768 tokens.

The harness makes up for those limits (Part III). The next chapter builds the model.
