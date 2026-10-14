# Part III: Building the Body

## 10. What a Harness Is

Our model can hold a conversation. Ask it to fix the failing tests, and it will tell you, at best, what it would do. It can't open a file. It can't run the tests. It can't remember yesterday. It doesn't know where it is or what day it is. Everything it lacks, the harness provides.

The harness is everything around the model. It turns the model's tokens into actions, and what happened back into tokens. Its five parts were introduced in Chapter 3. Here they are again, as the loop they make:

1. **Input** takes in a request from a person, or the result of an action.
2. **Context** gathers what the model needs to see this time.
3. **The model interface** hands that to the model, and brings back what it writes.
4. **Output** shows the model's words, or carries out the action it asked for.
5. **Control flow** decides what happens next. If an action ran, its result goes back to input, and the loop goes again. If not, it hands back to the person, or stops.

Control flow holds the other four: it's the loop they run in.

### Building around a borrowed mind

We'll build the harness one part at a time, and watch what each part adds. To see each part's effect clearly, the mind inside needs to be capable. Ours, at 600 million numbers, makes enough mistakes of its own that it would hide what the harness is doing. So, as with pre-training, we borrow: we build the body around **Claude Sonnet**, a model built at scale, reached over the internet. Once the body is built and proven, our own model moves in (Part IV), and we'll see exactly how far it has to go.

This is possible because only one part of the harness, the model interface, knows which model is inside. Everything else deals in plain things: messages, requests to act, and results. Swapping minds means changing one part.

### Building outward

We build the parts in the order information flows, outward from the model: first reach it, then let someone ask it something, then let it act, then let it go again, and finally tell it what it is. The agent is called **quark**. A quark is one of the smallest particles there is, and quark is meant to be the smallest agent: the five parts and nothing more.

Every version gets the same job: the shopping-basket project with the failing test, and the same request: *"The tests are failing. Find out why and fix it."*

In what follows, `>` is what a person typed, `<` is what quark said, and `$` is a command it ran.
