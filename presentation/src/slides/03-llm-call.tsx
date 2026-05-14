import { Slide, Heading, Text, CodePane, Notes } from "spectacle";
import llmCallSync from "@examples/llm_call_sync.py?raw";
import llmCallAsync from "@examples/llm_call_async.py?raw";

export function ModuleTwoTitleSlide() {
  return (
    <Slide>
      <Heading fontSize="32px" color="secondary">
        Module 2
      </Heading>
      <Heading fontSize="64px">An LLM call</Heading>
      <Text fontSize="24px" color="quaternary" margin="32px 0 0">
        One prompt in, one response out. No loop, no tools, no state between calls.
      </Text>
    </Slide>
  );
}

export function MessagesAPISlide() {
  return (
    <Slide>
      <Heading fontSize="40px">The Messages API</Heading>
      <Text fontSize="22px">One HTTP POST per call, one JSON response.</Text>
      <CodePane language="text">{`Fields:
  model        — which Claude model
  max_tokens   — cap on the response length
  system       — system prompt (applies to the whole conversation)
  messages     — list of { role, content } turns

Response:
  content      — list of blocks (text, tool_use, ...)`}</CodePane>
    </Slide>
  );
}

export function SyncCallSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">Sync — llm_call_sync.py</Heading>
      <CodePane language="python" showLineNumbers={false}>
        {llmCallSync}
      </CodePane>
      <Text fontSize="18px" color="secondary" margin="16px 0 0">
        Blocks until the full response is ready, then prints it.
      </Text>
    </Slide>
  );
}

export function StreamingMattersSlide() {
  return (
    <Slide>
      <Heading fontSize="40px">Why streaming matters</Heading>
      <Text fontSize="24px">
        <code>messages.create</code> waits for the full response before printing anything.
      </Text>
      <Text fontSize="24px" margin="32px 0 0">
        <strong>Streaming</strong> sends each chunk as the model generates it. Total
        latency stays the same; <em>time to first token</em> drops to near-instant.
      </Text>
      <Notes>
        For interactive use, that's the difference between an app that feels frozen and one
        that feels alive.
      </Notes>
    </Slide>
  );
}

export function AsyncStreamingSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">Async streaming — llm_call_async.py</Heading>
      <CodePane language="python" showLineNumbers={false}>
        {llmCallAsync}
      </CodePane>
      <Text fontSize="18px" color="secondary" margin="16px 0 0">
        The shape every script downstream of this module follows.
      </Text>
    </Slide>
  );
}

export function StreamingForAgentsSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">"Streaming doesn't fit for agents" — half-truth</Heading>
      <Text fontSize="22px">
        You can't dispatch tools <em>mid-stream</em>. But you can stream the text for UX
        while the SDK collects the structured response in the background:
      </Text>
      <CodePane language="python">{`async with client.messages.stream(...) as stream:
    async for text in stream.text_stream:
        print(text, end="", flush=True)
    response = await stream.get_final_message()  # full Message, tool_use blocks and all

# Dispatch tools from response.content here — no race.`}</CodePane>
      <Text fontSize="20px" color="quinary" margin="24px 0 0">
        Every example downstream uses <code>async</code> streaming.
      </Text>
    </Slide>
  );
}
