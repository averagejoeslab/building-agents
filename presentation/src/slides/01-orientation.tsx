import { Slide, Heading, Text, UnorderedList, ListItem, FlexBox, Box } from "spectacle";
import { Mermaid } from "../components/Mermaid";

export function DisciplineSlide() {
  return (
    <Slide>
      <Heading fontSize="44px">What is agentic engineering?</Heading>
      <Text fontSize="28px" color="quaternary">
        The discipline of building agentic systems.
      </Text>
      <UnorderedList fontSize="22px">
        <ListItem>Selecting the model</ListItem>
        <ListItem>Building the control flow</ListItem>
        <ListItem>Architecting memory</ListItem>
        <ListItem>Managing context</ListItem>
        <ListItem>Designing tools</ListItem>
        <ListItem>Handling safety / guardrails</ListItem>
        <ListItem>Setting up observability</ListItem>
        <ListItem>Building evaluations</ListItem>
        <ListItem>Optimizing the system (cost, latency, prompt tuning)</ListItem>
      </UnorderedList>
    </Slide>
  );
}

export function WhatAreAgenticSystemsSlide() {
  return (
    <Slide>
      <Heading fontSize="44px">What are agentic systems?</Heading>
      <Text fontSize="26px">
        Systems that can act on their own, without human intervention.
      </Text>
      <Text fontSize="26px" margin="40px 0 0">
        In modern agentic systems, this <strong>agency is provided by an LLM</strong>{" "}
        coordinating calls to accomplish a goal.
      </Text>
    </Slide>
  );
}

export function WorkflowsVsAgentsSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">Two shapes of agentic system</Heading>
      <FlexBox alignItems="flex-start" justifyContent="space-around" width="100%">
        <Box width="48%">
          <Heading fontSize="24px" color="quaternary">
            Workflow — code decides
          </Heading>
          <Text fontSize="18px" color="secondary">
            Prescriptive code paths define the sequence.
          </Text>
          <Mermaid>{`flowchart LR
            In[Input] --> W1[LLM] --> W2[LLM] --> W3[LLM] --> Out[Output]`}</Mermaid>
        </Box>
        <Box width="48%">
          <Heading fontSize="24px" color="quinary">
            Agent — model decides
          </Heading>
          <Text fontSize="18px" color="secondary">
            The model picks the next step from its distribution.
          </Text>
          <Mermaid>{`flowchart LR
            In[Input] --> A1[LLM]
            A1 --> A2{Tool?}
            A2 -->|yes| A3[Execute] --> A1
            A2 -->|no| Out[Output]`}</Mermaid>
        </Box>
      </FlexBox>
    </Slide>
  );
}

export function AverageJoesStanceSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">The purist stance</Heading>
      <Text fontSize="26px">
        A <strong>real agent has autonomy over its own control flow</strong> — the model
        decides what tool to call, what to do with the result, and when the task is done.
      </Text>
      <Text fontSize="22px" color="secondary" margin="40px 0 0">
        Workflows are outside the scope of what follows.
      </Text>
      <Mermaid>{`flowchart LR
        A[Agent — model decides] -->|freeze the path| W[Workflow — code decides]
        W -.cannot derive.-> A`}</Mermaid>
    </Slide>
  );
}
