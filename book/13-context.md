## 13. Context: What It Knows

**Context** is everything the model is shown each time it's asked to write. It's the agent's **working memory**: whatever is in it, the agent has in mind; whatever isn't, it doesn't. And because the model remembers nothing between uses, the harness assembles it fresh, every time.

### Parts of a context

A context is laid out in parts, and the model was trained to treat each part differently:

- **The system prompt**, also called the **instructions**: who the agent is and how it should work. The model was trained to give this the most weight.
- **The tools**: what the agent can do, and how to ask.
- **The conversation**: what people said, what the agent said and did, and what each action returned.

### The smallest useful context

The first version of quark's context adds one sentence of instructions:

> You are quark, an agent. You act through bash, in /tmp/shop. Today is 2026-10-07.

Its name, its body, where it is, and what day it is. Ask again:

> \> Who are you, and where are you working?
> < I'm quark, an agent that works by running shell commands through bash. My working directory is /tmp/shop. Today's date is 2026-10-07.

No commands needed. It knew.

That's the balance context has to strike. **Too little,** and the agent wastes steps finding things out, or guesses. **Too much,** and every request costs more, and what matters gets buried in what doesn't. The goal is the minimum it needs to act well, on whatever it's asked.

That's all five parts. With a model in it, it's an agent.

### A self model

As an agent grows more capable, its instructions grow into a picture of itself: a **self model**. quark's final instructions follow the same map as Chapter 3:

- **Identity:** who it is, and that it shares the world with other selves: people, and other agents.
- **Mind:** its context window, where its thinking happens, and the fact that it's summarized when it fills.
- **Body:** bash, its one means of acting and observing; where it runs; what it's allowed to do.
- **Loop:** observe, think, act, repeat.
- **Memory:** its three long-term memories, *semantic* (facts), *procedural* (how-tos) and *episodic* (what happened), where each lives, and how to read and write each one.
- **World:** where it is, and what day it is.
- **Other selves:** who else is there, and how to reach them.
- **How to act:** prefer the lightest action that does the job; ground what it says in what it observes, from the nearest source outward: what's already in mind, then memory, then the world, then asking a person.
- **Its own workings:** the harness's own code, so it knows how it works.

Written from the agent's own point of view, the self model tells the model what it is, so it never has to guess. It also costs: quark's final instructions run to about 9,400 tokens, sent with every request. The next chapter has to deal with that, among other things.

### Too long to send

A conversation grows with every step, and the context window has a limit. When a conversation gets too long to send, the harness has to make room. quark **summarizes** the older part: a model writes a short account of it, and the account takes its place. Nothing is truly lost, because, as the next chapter shows, every original message is kept on disk.

quark works. In the control-flow run, it found the bug, fixed it, ran the tests and committed. But look at how. It changed the code and committed without asking. Close the window, and the conversation is gone. A command that never finishes would hang it forever, and nothing records what it did. You wouldn't leave it running on its own.
