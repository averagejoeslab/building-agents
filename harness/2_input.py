# /// script
# dependencies = ["anthropic"]
# ///
from anthropic import Anthropic

model = Anthropic()


def request_response(context):
    return model.messages.create(model="claude-sonnet-5-5", max_tokens=16384, **context)


def capture_input():
    return input("\n> ")


response = request_response({"messages": [{"role": "user", "content": capture_input()}]})
print(response.model_dump_json(indent=2))
