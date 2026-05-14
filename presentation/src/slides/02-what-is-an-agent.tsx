import { Slide, Heading, Text, Notes, Box, FlexBox } from "spectacle";
import { Mermaid } from "../components/Mermaid";
import { Triad } from "../components/Triad";
import { Timeline } from "../components/Timeline";
import { Code } from "../components/Code";
import { colors } from "../theme";

export function ModuleOneTitleSlide() {
  return (
    <Slide>
      <Heading fontSize="32px" color="secondary">
        Module 1
      </Heading>
      <Heading fontSize="64px">What is an agent?</Heading>
      <Text fontSize="24px" color="quaternary" margin="32px 0 0">
        A system that can think, act, and observe — without human intervention.
      </Text>
    </Slide>
  );
}

export function ThreeComponentsSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">The three components</Heading>
      <Text fontSize="18px" color="secondary" margin="-8px 0 0">
        An agent is built from exactly three primitives. Everything else is harness.
      </Text>
      <Triad
        center="Agent"
        centerSub=""
        nodes={[
          { label: "LLM call", sublabel: "the reasoning engine" },
          { label: "Loop", sublabel: "Think · Act · Observe" },
          { label: "Tools", sublabel: "means of acting" },
        ]}
      />
    </Slide>
  );
}

export function TAOLoopSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">The TAO loop</Heading>
      <Mermaid>{`flowchart LR
        Start[User input] --> Think[THINK<br/>LLM call]
        Think --> Branch{Tool call?}
        Branch -->|yes| Act[ACT<br/>Execute tool]
        Act --> Observe[OBSERVE<br/>Result into context]
        Observe --> Think
        Branch -->|no| End[Response to user]
        style Think fill:#21262d,stroke:#58a6ff,color:#e6edf3
        style Act fill:#21262d,stroke:#3fb950,color:#e6edf3
        style Observe fill:#21262d,stroke:#f0883e,color:#e6edf3`}</Mermaid>
      <Text fontSize="18px" color="secondary" margin="20px 0 0">
        Also known as the <strong>ReAct loop</strong> — Yao et al., 2022.
      </Text>
    </Slide>
  );
}

const toolCode = `def read(path: str) -> str:
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"error: {e}"`;

const schemaCode = `{
  "name": "read",
  "description": "Read the contents of a file",
  "input_schema": {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
  },
}`;

export function ToolShapeSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">A tool has two parts</Heading>
      <Text fontSize="16px" color="secondary" margin="-8px 0 4px">
        Function does the work · Schema tells the model how to call it
      </Text>
      <FlexBox alignItems="flex-start" justifyContent="space-between" width="100%">
        <Box width="48%">
          <Text fontSize="16px" color="quinary" margin="0 0 6px">
            <strong>Function</strong> — language-specific (Python here)
          </Text>
          <Code language="python" fontSize={14}>{toolCode}</Code>
        </Box>
        <Box width="48%">
          <Text fontSize="16px" color="quaternary" margin="0 0 6px">
            <strong>Schema</strong> — JSON Schema, cross-language
          </Text>
          <Code language="json" fontSize={14}>{schemaCode}</Code>
        </Box>
      </FlexBox>
      <Text fontSize="14px" color="secondary" margin="14px 0 0" textAlign="center">
        <strong>On error, return a string</strong> — the model self-corrects.
        Raising kills the loop.
      </Text>
      <Notes>
        Cross-language: the function is Python here but could be TypeScript / Go /
        Rust — only the implementation changes; the schema is the same shape.
      </Notes>
    </Slide>
  );
}

export function ConcreteTraceSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">A concrete trace</Heading>
      <Text fontSize="16px" color="secondary" margin="-8px 0 8px">
        User: <em>"Find and summarize the TODOs in this codebase"</em>
      </Text>
      <Timeline
        duration={6}
        units="s"
        tracks={[
          {
            label: "THINK",
            sublabel: "LLM",
            color: colors.quaternary,
            events: [
              { at: 0.2, label: "I'll grep for TODOs", emphasis: true },
              { at: 2.4, label: "Read auth.ts" },
              { at: 4.6, label: "Enough to summarize" },
              { at: 5.6, label: "STOP" },
            ],
          },
          {
            label: "ACT",
            sublabel: "tool calls",
            color: colors.quinary,
            shaded: [
              { from: 0.5, to: 1.4, label: "grep" },
              { from: 2.7, to: 3.6, label: "read" },
            ],
          },
          {
            label: "OBSERVE",
            sublabel: "tool_result",
            color: colors.workflow,
            shaded: [
              { from: 1.4, to: 2.2, label: "47 hits across 12 files" },
              { from: 3.6, to: 4.4, label: "auth.ts contents" },
            ],
          },
        ]}
        highlightLabel="The model chose every action, read every result, and decided when to stop."
      />
    </Slide>
  );
}
