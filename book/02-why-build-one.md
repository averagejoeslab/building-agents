## 2. Why Build One

A language model on its own answers questions. Ask it how to fix failing tests, and it tells you what to look for. Then *you* open the files, *you* run the tests, *you* read the error, *you* make the change, and *you* run the tests again. The model advised. You did the work.

An agent does the work. You hand it the job, and it does the looking, the running, the reading, the changing, and the checking, one step at a time, deciding each next step from what the last one showed. That's the difference between asking a knowledgeable friend for directions and asking them to drive.

People build agents for the same reasons they hire help:

- **The work takes many steps.** Fixing a bug, filing a report, moving a website, answering a customer: each is a chain of small decisions, where each step depends on what the last one found. An agent can follow the chain without someone guiding every link.
- **The work happens in tools.** Most real work lives in files, programs, websites and systems. An agent can use those tools directly, instead of telling a person what to type.
- **The steps can't all be planned ahead.** A script follows the same steps every time. An agent decides as it goes, so it can handle a failing test it's never seen, in a project it's never opened.
- **There's more work than people.** An agent can work at any hour, on many jobs at once, and doesn't get bored by the hundredth one.

### Why build one from scratch

You don't have to. You can take a model someone else trained, wrap it in a harness someone else built, and have an agent this afternoon. Many good agents are made that way.

But building one from scratch is the way to *understand* one. When an agent fails, the cause could be in the model: it didn't know something, or never learned a habit. Or it could be in the harness: it couldn't see what it needed, or couldn't do what it decided. Or it could be in how the two fit together: the model was trained for a different body than the one it's in. You can only tell these apart if you know what each part is and how it's made. Chapter 19 does exactly this diagnosis, gap by gap, and every diagnosis depends on knowing where each piece came from.

And building from scratch is how the frontier labs do it. They don't take a model and a harness off the shelf. They design the model, train it in stages, build the harness the agent will live in, and then train the model *inside that harness*, so the mind learns to use the body it actually has. The best agents come from that last step, and it's the one least often explained.

### What "from scratch" means here

This book builds everything, but not everything at full size. The honest accounting:

| | Built here | Borrowed, and why |
|---|---|---|
| **Model architecture** | Yes: every part, in about 350 lines | Checked against Qwen's implementation to prove it's right |
| **Tokenizer** | Yes: the learning algorithm and the encoder | Qwen's learned merges are loaded for the large model |
| **Pre-training** | Yes, from random numbers, on 320,000 tokens | Qwen3-0.6B-Base's weights for the rest: 36 trillion tokens is beyond one computer |
| **Mid-training** | Yes | |
| **Instruction-tuning** | Yes: data pipeline, masking, training loop | Public datasets for the general conversation kinds |
| **Reinforcement learning** | Yes: the loop, the reward, the update | |
| **Harness** | Yes: every line | Claude Sonnet as the mind while the body is built |
| **Evaluation** | Yes: 32 tasks and their checks | |

Everything borrowed is swapped in through an interface we also built, so the swap is visible and reversible. Where our scale falls short of a lab's, the book says by how much, and what the lab does instead.
