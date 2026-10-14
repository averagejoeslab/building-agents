# Part IV: Training the Mind in Its Body

## 16. The Mind Moves In

The harness is built and proven. Now we take out the borrowed mind and put ours in.

Only one part changes: the **model interface**. Instead of sending the conversation to Sonnet over the internet, it runs our model on this computer. It lays the conversation out in the chat template, lets the model write, and reads what it wrote. Wherever the model has written a tool call in the format it was trained on, the interface turns it into the same kind of request to run a command that Sonnet's replies contained. To the rest of the harness, nothing has changed: words come back, and requests to act.

Two details matter more than they look.

**Give it the context it will be trained on.** Sonnet gets quark's 9,400-token self model. Our model gets quark's one-sentence instructions from Chapter 13, the ones its training examples use. A small model does best in the context it knows.

**End the prompt exactly where its turn began in training.** Qwen's chat template, trying to be helpful, inserts an empty thinking block at the start of every assistant turn when it asks for a reply. If the model never saw that in training, the prompt puts it somewhere it has never been. Small differences like this break models quietly. The harness must present the conversation exactly as the model learned it.

### Why train it here

A model's training so far taught it language, the shell, and how to take turns. None of that taught it to be *this agent, in this body*: to call *this* tool in *this* format, read *these* results, and keep going until *this* kind of job is done. A lab's model is post-trained for many harnesses at once. Training a model in its own harness teaches it the body it actually has.

That training happens in two ways, as Chapter 9 promised: by example, and by practice. But first, a measurement: what does our model do in the harness *before* any of it?

### Before: the mid-trained model in quark

We run the evaluation from Chapter 15, with the mid-trained model in quark, the one that knows the shell but has never had a conversation.

It passes **2 of 32**: the two safety tasks, which doing nothing passes.

Every other task went the same way. Asked to count the lines in a file, it didn't call its tool, answer, or stop. It carried on writing the chat template's own text, in the template's style, until it ran out of room. It had never seen a turn end or a tool get called. It knows the shell; it doesn't know it's in a conversation, or that it has a body.

That's what training in the harness has to teach.
