import sys
from anthropic import Anthropic

client = Anthropic()

def ask(prompt):
    reply = client.messages.create(model="claude-sonnet-5-5", max_tokens=2048, messages=[{"role": "user", "content": prompt}])
    return next(b.text for b in reply.content if b.type == "text")

task = " ".join(sys.argv[1:]) or input("> ")
draft = ask(f"Do this task. Reply with only the result.\n\n{task}")
for round in range(1, 4):
    print(f"--- draft {round} ---\n{draft}\n")
    verdict = ask(f"Task:\n{task}\n\nDraft:\n{draft}\n\nCheck the draft against every requirement in the task. If it meets all of them, reply with only PASS. Otherwise list what to fix.")
    if verdict.strip() == "PASS":
        print("[evaluator: pass]")
        break
    print(f"--- evaluator ---\n{verdict}\n")
    draft = ask(f"Task:\n{task}\n\nDraft:\n{draft}\n\nFeedback:\n{verdict}\n\nRewrite the draft to fix everything in the feedback. Reply with only the new draft.")
else:
    print("[stopped: 3 rounds without a pass]")
