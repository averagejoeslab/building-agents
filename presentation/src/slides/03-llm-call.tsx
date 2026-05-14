import { Slide, Heading, Text, Notes, FlexBox, Box } from "spectacle";
import { AnatomyBox } from "../components/AnatomyBox";
import { Timeline } from "../components/Timeline";
import { SequenceDiagram } from "../components/SequenceDiagram";
import { Code } from "../components/Code";
import { colors } from "../theme";
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
        One prompt in, one response out. No loop, no tools, no state.
      </Text>
    </Slide>
  );
}

export function MessagesAPISlide() {
  return (
    <Slide>
      <Heading fontSize="36px">The Messages API</Heading>
      <Text fontSize="16px" color="secondary" margin="-8px 0 12px">
        One HTTP POST per call. One JSON response.
      </Text>
      <FlexBox justifyContent="space-around" alignItems="flex-start" width="100%">
        <AnatomyBox
          title="POST /v1/messages"
          subtitle="Request body"
          accent={colors.quaternary}
          fields={[
            { name: "model", type: "string", description: "Which Claude model to call" },
            { name: "max_tokens", type: "int", description: "Cap on the response length" },
            { name: "system", type: "string", description: "System prompt for the call" },
            { name: "messages", type: "array", description: "List of { role, content } turns" },
            { name: "tools", type: "array?", description: "Tool schemas (Module 5+)" },
          ]}
        />
        <AnatomyBox
          title="Message"
          subtitle="Response body"
          accent={colors.quinary}
          fields={[
            { name: "id", type: "string", description: "Unique message id" },
            { name: "role", type: "\"assistant\"", description: "Always assistant in responses" },
            { name: "content", type: "Block[]", description: "Text and/or tool_use blocks" },
            { name: "stop_reason", type: "string", description: "end_turn | tool_use | ..." },
            { name: "usage", type: "object", description: "Token counts in / out" },
          ]}
        />
      </FlexBox>
    </Slide>
  );
}

export function SyncCallSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">Sync — llm_call_sync.py</Heading>
      <FlexBox alignItems="flex-start" justifyContent="space-between" width="100%">
        <Box width="58%">
          <Code language="python" fontSize="15px">{llmCallSync}</Code>
        </Box>
        <Box width="40%">
          <Text fontSize="16px" color="secondary" margin="0 0 8px">
            Wall-clock for one call:
          </Text>
          <Timeline
            duration={5}
            units="s"
            tracks={[
              {
                label: "sync",
                color: colors.workflow,
                shaded: [{ from: 0.1, to: 4.4, label: "blocked — waiting for full response" }],
                events: [
                  { at: 4.5, label: "all tokens print", emphasis: true },
                ],
              },
            ]}
          />
          <Text fontSize="13px" color="secondary" margin="10px 0 0">
            Nothing reaches the user until the model is done.
          </Text>
        </Box>
      </FlexBox>
    </Slide>
  );
}

export function StreamingMattersSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">Why streaming matters</Heading>
      <Text fontSize="18px" color="secondary" margin="-8px 0 4px">
        Same total latency. Same final text. <strong style={{ color: colors.quinary }}>Time-to-first-token drops to near-zero.</strong>
      </Text>
      <Timeline
        duration={5}
        units="s"
        tracks={[
          {
            label: "sync",
            sublabel: "messages.create",
            color: colors.workflow,
            shaded: [{ from: 0.1, to: 4.4, label: "blocked" }],
            events: [{ at: 4.5, label: "full text dumps", emphasis: true }],
          },
          {
            label: "stream",
            sublabel: "messages.stream",
            color: colors.quinary,
            events: [
              { at: 0.15, label: "tok", emphasis: true },
              { at: 0.4, label: "" },
              { at: 0.65, label: "" },
              { at: 0.9, label: "" },
              { at: 1.2, label: "" },
              { at: 1.5, label: "" },
              { at: 1.8, label: "" },
              { at: 2.1, label: "" },
              { at: 2.4, label: "" },
              { at: 2.7, label: "" },
              { at: 3.0, label: "" },
              { at: 3.3, label: "" },
              { at: 3.6, label: "" },
              { at: 3.9, label: "" },
              { at: 4.2, label: "" },
              { at: 4.5, label: "stop" },
            ],
          },
        ]}
        highlightLabel="For interactive use, this is the difference between an app that feels frozen and one that feels alive."
      />
    </Slide>
  );
}

export function AsyncStreamingSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">Async streaming — llm_call_async.py</Heading>
      <FlexBox alignItems="flex-start" justifyContent="space-between" width="100%">
        <Box width="55%">
          <Code language="python" fontSize="13px">{llmCallAsync}</Code>
        </Box>
        <Box width="43%">
          <Text fontSize="14px" color="secondary" margin="0 0 8px">
            On the wire:
          </Text>
          <SequenceDiagram
            lanes={[{ label: "Your program" }, { label: "Anthropic API" }]}
            events={[
              { from: 0, to: 1, label: "POST /v1/messages (stream)", kind: "call" },
              { from: 1, to: 0, label: "message_start", kind: "stream" },
              { from: 1, to: 0, label: "content_block_delta", kind: "stream" },
              { from: 1, to: 0, label: "content_block_delta", kind: "stream" },
              { from: 1, to: 0, label: "… (many)", kind: "stream" },
              { from: 1, to: 0, label: "message_stop", kind: "return" },
              { from: 0, to: 0, label: "stream.get_final_message()", kind: "note" },
            ]}
          />
        </Box>
      </FlexBox>
    </Slide>
  );
}

export function StreamingForAgentsSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">"Streaming doesn't fit for agents" — half-truth</Heading>
      <Text fontSize="15px" color="secondary" margin="-8px 0 6px">
        You can't dispatch tools <em>mid-stream</em>. But you can stream the text live
        while the SDK assembles the structured response in the background.
      </Text>
      <SequenceDiagram
        lanes={[{ label: "User UI" }, { label: "SDK" }, { label: "API" }, { label: "Tools" }]}
        events={[
          { from: 1, to: 2, label: "stream request", kind: "call" },
          { from: 2, to: 1, label: "text deltas (stream)", kind: "stream" },
          { from: 1, to: 0, label: "print live", kind: "stream" },
          { from: 2, to: 1, label: "tool_use deltas (buffered)", kind: "stream" },
          { from: 2, to: 1, label: "message_stop", kind: "return" },
          { from: 1, to: 1, label: "get_final_message() → full Message", kind: "note" },
          { from: 1, to: 3, label: "dispatch tools (after stream done)", kind: "call" },
        ]}
      />
      <Notes>
        Every example downstream of this module uses async streaming. The chatbots
        stream text and that's the end of the turn; the agents stream the model's
        narration, then await get_final_message and dispatch tool calls.
      </Notes>
    </Slide>
  );
}
