import sys
from anthropic import Anthropic
read = input                                             # a person's input; the name input is for whatever comes in

client = Anthropic()

def ask(prompt):
    output = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, messages=[{"role": "user", "content": prompt}])
    return next(b.text for b in output.content if b.type == "text")

input = " ".join(sys.argv[1:]) or read("> ")
draft = ask(f"Do this task. Reply with only the result.\n\n{input}")
for round in range(1, 4):
    print(f"--- draft {round} ---\n{draft}\n")
    verdict = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nCheck the draft against every requirement in the task. If it meets all of them, reply with only PASS. Otherwise list what to fix.")
    if verdict.strip() == "PASS":
        print("[evaluator: pass]")
        break
    print(f"--- evaluator ---\n{verdict}\n")
    draft = ask(f"Task:\n{input}\n\nDraft:\n{draft}\n\nFeedback:\n{verdict}\n\nRewrite the draft to fix everything in the feedback. Reply with only the new draft.")
else:
    print("[stopped: 3 rounds without a pass]")
