# Part II: Building the Mind

## 4. What a Model Does

A language model predicts what comes next.

It doesn't read words the way you do. It reads **tokens**: small pieces of text, each one a number. A common word is usually one token. A rare word might be several. Spaces and punctuation are part of tokens too.

Give a model some tokens, and it works out how likely every possible next token is. Then one is picked, it's added to the end, and the model goes again, now with one more token to read. Token by token, it writes. It stops when the next most likely thing is a special token that means *the end*.

> **TokensOut = Model(TokensIn)**

That's the whole job. Everything a model seems to know, everything it seems to do, comes from doing that one thing very well.

### One prediction, all the way through

Here is a real model predicting a real next token. The model is **Qwen3-0.6B**, an open model with about 600 million numbers inside it, whose design this book builds. The text is *"The capital of France is"*.

1. **Text becomes tokens.** The text is split into five tokens, and each becomes a number: 785, 6722, 315, 9625, 374.
2. **Tokens become meanings.** Each token is turned into a list of 1,024 numbers that stands for what it means, and is marked with where it sits in the text.
3. **Meanings take in their context.** The lists pass through 28 layers. In each one, every token looks back at the tokens before it, takes in what it needs, and then is worked on further. By the end, each token's numbers stand for what it means *here*, in this sentence.
4. **The last position predicts.** The final token's numbers are compared with every token the model knows, all 151,936 of them, giving each a score: how likely it is to come next.
5. **One is picked.** The highest score here is *" Paris"*. It's added to the end, and the whole thing runs again to predict what follows.

Asked to keep going, the same model writes: *"The capital of France is Paris. The capital of Germany is Berlin. The capital of…"* It has learned what tends to follow what, so well that it reads like knowledge.

### Picking the next token

The model doesn't decide which token comes next. It gives every token a score. Something else picks.

Always picking the highest score makes a model predictable and dull, and prone to repeating itself. So the pick usually involves some chance: likely tokens are picked often, less likely ones sometimes, very unlikely ones never. A setting called *temperature* controls how adventurous that is. This is why you can ask a model the same thing twice and get two different answers.

### What a model can't do

Notice what's missing. A model:

- **can't see.** It knows only the tokens it's given.
- **can't remember.** Every use starts fresh. A conversation only seems remembered because the whole thing is sent again each time.
- **can't act.** It writes tokens. If those tokens spell out a command, nothing runs it.
- **can only take in so much.** There's a limit to how many tokens it can read at once, its **context window**.

Those limits are why an agent needs a harness. But first, we need a model. The next chapter builds one.
