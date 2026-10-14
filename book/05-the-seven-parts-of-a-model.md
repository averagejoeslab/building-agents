## 5. The Seven Parts of a Model

Every model of this kind, from the smallest to the largest in the world, is built from the same seven parts. Model families differ in the details of each one, but not in what the parts are.

| Part | What it does |
|---|---|
| **Tokenizer** | Turns text into tokens, and back |
| **Embedding** | Turns each token into a list of numbers that stands for its meaning |
| **Position** | Marks where each token is |
| **Attention** | Lets each token take in the ones before it |
| **Block** | Attention, then a small network that works on the result; stacked many times |
| **Output head** | Gives a score to every possible next token |
| **Generation** | Picks the next token, adds it, and goes again |

We build Qwen3's version of each, so that once ours is built, we can load the numbers Qwen trained into it, and check that our model does exactly what theirs does.

### Tokenizer

A model can't read letters, only numbers. The tokenizer decides what the pieces are.

It learns them from text. It starts with every single byte as its own token, then counts which two tokens sit next to each other most often, and makes that pair a new token. Then it counts again, and merges again, thousands of times. Common words end up as one token; rare words as several pieces. To read new text, it splits it into bytes and applies the same merges, most common first.

### Embedding

Each token gets a row of numbers, its **embedding**. Qwen3-0.6B gives each one 1,024 numbers. At first they're random. Training moves them, until tokens that are used in similar ways end up with similar numbers. The numbers come to stand for meaning.

### Position

Embeddings say what each token is, but not where. *Dog bites man* and *man bites dog* have the same tokens. Qwen3 marks position by turning each token's numbers through an angle that grows along the text, so that how two tokens line up depends on how far apart they are.

### Attention

This is the part that lets a token take in its context. Each token asks three things of itself: *what am I looking for?*, *what do I offer?*, and *what do I carry?* Every token's question is compared with every earlier token's offer. Where they match well, the token takes in a large share of what that earlier token carries; where they don't, little.

Two rules keep it honest. A token can only look *back*, never ahead, because when the model writes, the future hasn't been written yet. And it does this many times side by side, sixteen in Qwen3-0.6B, each free to look for something different: one might track grammar, another names, another what a pronoun refers to.

### Block

A **block** is attention followed by a small network that works on what attention gathered. Each adds to what came in rather than replacing it, so nothing is lost on the way through. Blocks are stacked: Qwen3-0.6B has 28. Each pass deepens what every token's numbers mean in context.

### Output head

After the last block, the final token's numbers are compared with every token's embedding. The closer the match, the higher the score. That's 151,936 scores: one for every token the model knows.

### Generation

Generation turns scores into text: pick a token (with a little chance, as the last chapter described), add it to the end, and run again. To avoid redoing work, the model keeps what it worked out for earlier tokens, and only computes the new one.

### Checking it

That's the whole model: about 180 lines of code. Built from nothing, it's an empty shape: its numbers are random, and it writes noise.

To know it's built right, we load the trained numbers Qwen published for Qwen3-0.6B into our code, and compare it with Qwen's own. At every one of 198 positions in a test text, ours picks the same next token as theirs, and its scores differ from theirs by at most 0.00014. Given *"The capital of France is"*, it writes *" Paris."*

A model also ships with more than its numbers: its tokenizer, a **chat template** that lays out a conversation the way it was trained to read one, and settings for generating. Miss one, and the model breaks quietly, writing worse without saying why. So each is loaded from its own file and checked against Qwen's: the same tokens, the same template, the same predictions.

We have a mind. It knows nothing yet. The next chapter is about how a model learns.
