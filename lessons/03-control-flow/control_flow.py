import subprocess, sys
from anthropic import Anthropic

client = Anthropic()
tools = [{"name": "bash", "description": "Run shell command", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]

def call(messages, **request):
    return client.messages.create(model="claude-sonnet-5-5", max_tokens=16384, messages=messages, **request).content

def ask(prompt):
    return "".join(block.text for block in call([{"role": "user", "content": prompt}]) if block.type == "text")

def workflow(input):                                     # your code decides the next step: draft, review, rewrite, stop
    draft = ask(f"Do this task. Reply with only the result.\n\n{input}")
    print(f"--- draft ---\n{draft}\n")
    review = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nCheck the draft against every requirement in the task. List what to fix, or say it's fine.")
    print(f"--- review ---\n{review}\n")
    output = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nReview:\n{review}\n\nRewrite the draft to fix everything in the review. Reply with only the new draft.")
    print(f"--- final ---\n{output}")

def agent(input):                                        # the model decides the next step: ask for a tool, or stop
    messages = [{"role": "user", "content": input}]
    while True:
        output = call(messages, tools=tools)
        messages.append({"role": "assistant", "content": output})
        input = []
        for block in output:
            if block.type == "text": print(block.text)
            if block.type == "tool_use":
                print(f"$ {block.input['cmd']}")
                done = subprocess.run(block.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                print(done.stdout)
                input.append({"type": "tool_result", "tool_use_id": block.id, "content": done.stdout or f"(exit {done.returncode})"})
        if not input: break                              # no tool request: the model is done
        messages.append({"role": "user", "content": input})

mode, input = sys.argv[1], " ".join(sys.argv[2:])
workflow(input) if mode == "workflow" else agent(input)
