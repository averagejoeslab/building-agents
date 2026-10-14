## 8. Mid-training: Knowing the Job

**Goal:** be good at what matters for the job.

Mid-training is the same task as pre-training, predicting every next token, but on text chosen for what the model will need. A lab might mid-train on code, maths, long reasoning, or recordings of agents at work. The model already knows language; mid-training deepens what it knows about the job.

### Choosing the data

Our agent will act through the **shell**, the text window where a person types commands to a computer. So it needs to know shell commands well. Our data is [tldr-pages](https://github.com/tldr-pages/tldr): 6,787 short, freely licensed pages about shell commands, each a plain-English line and the command that does it. For example:

> Create a gzipped archive and write it to a file:
> `tar czf path/to/target.tar.gz path/to/file1 path/to/file2 ...`

Two rules shape the data before any training happens.

**Hold some out.** 200 pages are set aside, never trained on, to measure the stage.

**Keep it apart from the final exam.** The finished agent will be evaluated on a set of tasks (Chapter 15). Nothing the model trains on may resemble them, or the evaluation would measure memory instead of skill. So any page with an example too close to an evaluation task is left out. This is called **decontamination**, and every stage does it.

### Checking it

The stage gets two checks, before and after.

The first is **held-out loss**: how surprised the model is by the 200 pages it never saw.

The second is a **shell check**: can it name the right command? It's a base model, so it's asked by example. It sees a held-out page as the page shows it, with the page's other examples first, then the plain-English line of its last example, and the start of the command. It passes if it writes the right command with every word the page's has. The order of words and the exact values can vary between right answers, so the check asks for the words, not the exact string.

Mid-training runs a fixed 60 steps, about an eighth of the pages, once:

| | Held-out loss | Shell check |
|---|---|---|
| **Before: Qwen3-0.6B-Base** | 1.896 | 48/100 |
| **After 60 steps** | 1.411 | 53/100 |

It predicts the pages far better, and names the right command a little more often. The gap between those two numbers is itself a lesson: the loss is measured on every token of a page, mostly prose and placeholders, while the command is a few words, and the base model already knew most of them. A small dose of mid-training teaches the style of the pages more than new commands. A lab would give it far more.

### What it can't do yet

Our model knows language, and knows the shell a little better. But ask it to do something, and it won't. It continues text. It has never seen a conversation's turn end, or a request answered, or a tool called. Making it behave is the work of post-training.
