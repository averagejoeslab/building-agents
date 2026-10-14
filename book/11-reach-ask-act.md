## 11. Reach, Ask, Act

### Model interface: reach the mind

We have a model and no way to reach it. The **model interface** sends it a request and brings back its response. For Sonnet, that means sending the conversation over the internet, in the format its makers expect, and receiving its reply.

So we send it the job, written in ahead of time. It answers:

> I don't have access to your code, test files, or test output. Nothing came through in your message besides the request. …

Text in, text out. It can reason about failing tests in general, but it has nothing to reason about. And the request was written into the program: nobody can ask it anything else.

### Input: let someone ask

**Input** captures what comes in. The first kind is a person typing. Now anyone can type the request:

> \> The tests are failing. Find out why and fix it.
> I don't have the code or the test output yet, so I can't tell why the tests are failing. Could you share: …

The same answer. It can only talk. It can't look at a file.

### Output: let it act

The model can only write text, so acting works like this. We tell the model about a **tool**: its name, what it does, and what it needs to be told. Our agent gets one tool, **bash**, the shell: *run a shell command.* When the model wants to use it, instead of writing an answer, it writes a request: *run this command.* The model interface brings that request back as a separate piece of the response, marked as a tool call.

**Output** handles the response. Words are shown to the person. Tool calls are carried out: the command is run, and what it printed is collected.

Why one tool? Through the shell, an agent can do nearly anything a person at that computer can do: read and change files, run programs, run tests, use version control. One general tool keeps the harness simple, and the model already knows the shell from training. More tools can be added when one can't do a job, or can't do it safely.

Now it acts:

> \> The tests are failing. Find out why and fix it.
> < I'll start by exploring the project and running the tests.
> $ pwd; ls -la; git status 2>/dev/null | head

And then it stops.

The command ran, and printed a list of files. But nothing sent that list to the model. The model asked to look, the harness looked, and nobody told the model what was seen. What came back is new input from the world, and nothing carries it to the mind.

The fourth part closes that gap.
