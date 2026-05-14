import { Slide, Heading, Text, UnorderedList, ListItem, FlexBox } from "spectacle";

export function WhatsNextSlide() {
  return (
    <Slide>
      <Heading fontSize="44px">What's next in the curriculum</Heading>
      <UnorderedList fontSize="22px">
        <ListItem>
          <strong>M4 — Add memory</strong> → stateful chatbot (persistence + budget + recall)
        </ListItem>
        <ListItem>
          <strong>M5 — Add tools</strong> → stateful agent (TAO loop + registry + parallel
          dispatch)
        </ListItem>
        <ListItem>
          <strong>M6 — Add sandboxing</strong> → Docker-isolated bash
        </ListItem>
        <ListItem>
          <strong>M7 — Add guardrails</strong> → approval gates, loop bounds, retry
        </ListItem>
        <ListItem>
          <strong>M8 — Add observability</strong> → structured spans / JSONL traces
        </ListItem>
        <ListItem>
          <strong>M9 — Add evaluation</strong> → task suites, LLM-as-judge, regression
          testing
        </ListItem>
        <ListItem>
          <strong>M10 — Add performance</strong> → caching, threading, structured prompts
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
        <Text fontSize="20px" color="secondary" margin="60px 0 0">
          Build an agent, not a wrapper.
        </Text>
      </FlexBox>
    </Slide>
  );
}
