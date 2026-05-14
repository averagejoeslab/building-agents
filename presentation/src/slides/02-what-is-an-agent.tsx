import { Slide, Heading, Text, UnorderedList, ListItem, CodePane, Notes } from "spectacle";
import { Mermaid } from "../components/Mermaid";

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
      <Heading fontSize="40px">The three components</Heading>
      <UnorderedList fontSize="28px">
        <ListItem>
          <strong>An LLM call</strong> — the reasoning engine
        </ListItem>
        <ListItem>
          <strong>A loop</strong> (Think, Act, Observe) — turns single calls into sustained
          work
        </ListItem>
        <ListItem>
          <strong>Tools</strong> — the agent's means of acting on its environment
        </ListItem>
      </UnorderedList>
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
        Branch -->|no| End[Response to user]`}</Mermaid>
      <Text fontSize="20px" color="secondary" margin="24px 0 0">
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
        return f"error: {e}"

tools = [{
    "name": "read",
    "description": "Read the contents of a file",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}]`;

export function ToolShapeSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">A tool has two parts</Heading>
      <Text fontSize="22px" color="secondary">
        Function in your language + JSON Schema the model reads.
      </Text>
      <CodePane language="python">{toolCode}</CodePane>
      <Notes>
        Errors return as strings — the model can self-correct. A raised exception kills the
        loop.
      </Notes>
    </Slide>
  );
}

export function ConcreteTraceSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">A concrete trace</Heading>
      <CodePane language="text">{`User: "Find and summarize the TODOs in this codebase"

[THINK]    I'll search for TODO comments
[ACT]      grep("TODO", ".")
[OBSERVE]  src/auth.ts:42:  // TODO: session expiration
           src/auth.ts:87:  // TODO: rate limiting
           ...44 more matches
[THINK]    Most are in auth.ts — I'll read that file
[ACT]      read("src/auth.ts")
[OBSERVE]  [full file contents]
[THINK]    I have enough to summarize
[STOP]     "You have 47 TODOs across 12 files..."`}</CodePane>
      <Text fontSize="20px" color="secondary" margin="24px 0 0">
        The model chose every action, read every result, and decided when to stop.
      </Text>
    </Slide>
  );
}
