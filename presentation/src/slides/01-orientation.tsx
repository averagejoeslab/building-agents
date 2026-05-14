import { Slide, Heading, Text, FlexBox, Box } from "spectacle";
import { Mermaid } from "../components/Mermaid";
import { Radial } from "../components/Radial";
import { ComparisonPanel } from "../components/ComparisonPanel";
import { Spectrum } from "../components/Spectrum";
import { colors } from "../theme";

export function DisciplineSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">What is agentic engineering?</Heading>
      <Text fontSize="20px" color="quaternary" margin="-12px 0 0">
        The discipline of building agentic systems.
      </Text>
      <Radial
        center="Agentic"
        centerSub="Engineering"
        spokes={[
          { label: "Model", group: 0 },
          { label: "Control flow", group: 0 },
          { label: "Memory", group: 1 },
          { label: "Context", group: 1 },
          { label: "Tools", group: 1 },
          { label: "Safety", group: 2 },
          { label: "Observability", group: 2 },
          { label: "Evaluation", group: 2 },
          { label: "Optimization", group: 2 },
        ]}
        legend={[
          { label: "Foundational", color: colors.quaternary },
          { label: "Behavioral", color: colors.quinary },
          { label: "Operational", color: colors.workflow },
        ]}
      />
    </Slide>
  );
}

export function WhatAreAgenticSystemsSlide() {
  return (
    <Slide>
      <Heading fontSize="42px">What are agentic systems?</Heading>
      <Text fontSize="20px" color="secondary" margin="-8px 0 0">
        Systems that act on their own, without human intervention.
        In modern ones, the agency is provided by an LLM.
      </Text>
      <Box marginTop="24px">
        <ComparisonPanel
          left={{
            title: "Traditional software",
            subtitle: "deterministic — code decides",
            accent: colors.workflow,
            content: (
              <div style={{ fontFamily: colors.mono, fontSize: 16, lineHeight: 1.7 }}>
                <div>input → <b>function</b> → output</div>
                <div style={{ color: colors.secondary, marginTop: 12, fontFamily: colors.sans, fontSize: 14 }}>
                  Same input → same output. The control flow lives in your code.
                </div>
              </div>
            ),
          }}
          right={{
            title: "Agentic system",
            subtitle: "probabilistic — model decides",
            accent: colors.quinary,
            content: (
              <div style={{ fontFamily: colors.mono, fontSize: 16, lineHeight: 1.7 }}>
                <div>input → <b>LLM</b> → output</div>
                <div style={{ color: colors.secondary, marginTop: 12, fontFamily: colors.sans, fontSize: 14 }}>
                  Same input → distribution over outputs. The model coordinates LLM calls
                  to reach a goal without supervision.
                </div>
              </div>
            ),
          }}
        />
      </Box>
    </Slide>
  );
}

export function WorkflowsVsAgentsSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">Two shapes of agentic system</Heading>
      <FlexBox alignItems="flex-start" justifyContent="space-around" width="100%">
        <Box width="48%">
          <Heading fontSize="22px" color="workflow" style={{ color: colors.workflow }}>
            Workflow — code decides
          </Heading>
          <Text fontSize="15px" color="secondary">
            Prescriptive code paths define the sequence.
          </Text>
          <Mermaid>{`flowchart LR
            In[Input] --> W1[LLM] --> W2[LLM] --> W3[LLM] --> Out[Output]
            style W1 fill:#21262d,stroke:#f0883e,color:#e6edf3
            style W2 fill:#21262d,stroke:#f0883e,color:#e6edf3
            style W3 fill:#21262d,stroke:#f0883e,color:#e6edf3`}</Mermaid>
        </Box>
        <Box width="48%">
          <Heading fontSize="22px" style={{ color: colors.quinary }}>
            Agent — model decides
          </Heading>
          <Text fontSize="15px" color="secondary">
            The model picks the next step from its distribution.
          </Text>
          <Mermaid>{`flowchart LR
            In[Input] --> A1[LLM]
            A1 --> A2{Tool?}
            A2 -->|yes| A3[Execute] --> A1
            A2 -->|no| Out[Output]
            style A1 fill:#21262d,stroke:#3fb950,color:#e6edf3
            style A3 fill:#21262d,stroke:#3fb950,color:#e6edf3`}</Mermaid>
        </Box>
      </FlexBox>
    </Slide>
  );
}

export function AverageJoesStanceSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">The purist stance</Heading>
      <Text fontSize="20px" margin="-8px 0 0">
        A <strong>real agent has autonomy over its own control flow.</strong>{" "}
        Workflows are outside the scope of this curriculum.
      </Text>
      <Spectrum
        leftLabel="Workflow"
        rightLabel="Agent"
        points={[
          { position: 0.0, label: "Anthropic prompt chains", color: colors.workflow },
          { position: 0.35, label: "Cursor 2.0", sublabel: "parallel workers, no supervisor", color: colors.workflow },
          { position: 0.55, label: "Anthropic multi-agent", sublabel: "research mode", color: colors.quaternary },
          { position: 0.85, label: "Cognition / Devin", sublabel: "single-threaded agent", color: colors.quinary },
          { position: 1.0, label: "agenteng", sublabel: "this repo", color: colors.quinary },
        ]}
        highlightFrom={0.75}
        highlightTo={1.0}
        highlightLabel="Where this curriculum lives"
      />
    </Slide>
  );
}
