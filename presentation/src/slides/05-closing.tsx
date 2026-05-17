import { Slide, Heading, Text, UnorderedList, ListItem, FlexBox } from "spectacle";

export function WhatsNextSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">The rest of the harness</Heading>
      <Text fontSize="16px" color="secondary" margin="-8px 0 8px">
        Each remaining module adds one harness component.
      </Text>
      <UnorderedList fontSize="20px">
        <ListItem>
          <strong>M4 — Add memory</strong> → memory + context management
        </ListItem>
        <ListItem>
          <strong>M5 — Add tools</strong> → the tool / action layer (TAO loop, registry, parallel dispatch)
        </ListItem>
        <ListItem>
          <strong>M6 — Add sandboxing</strong> → execution environment (Docker isolation)
        </ListItem>
        <ListItem>
          <strong>M7 — Add guardrails</strong> → safety constraints (approval, loop bounds, retry)
        </ListItem>
        <ListItem>
          <strong>M8 — Add observability</strong> → structured tracing (JSONL spans)
        </ListItem>
        <ListItem>
          <strong>M9 — Add evaluation</strong> → test infrastructure (task suites, LLM-as-judge)
        </ListItem>
        <ListItem>
          <strong>M10 — Add performance</strong> → production hardening (caching, threading, structured prompts)
        </ListItem>
      </UnorderedList>
    </Slide>
  );
}

export function ClosingSlide() {
  return (
    <Slide>
      <FlexBox height="100%" flexDirection="column" justifyContent="center">
        <Heading fontSize="80px">Thank you.</Heading>
        <Text fontSize="24px" color="secondary" margin="32px 0 0">
          github.com/averagejoeslab/agenteng
        </Text>
        <Text fontSize="18px" color="secondary" margin="40px 0 0">
          A model is intelligence. A harness is the runtime.
        </Text>
        <Text fontSize="18px" color="secondary" margin="6px 0 0">
          Build the harness.
        </Text>
      </FlexBox>
    </Slide>
  );
}
