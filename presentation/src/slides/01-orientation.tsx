import { Slide, Heading, Text, FlexBox, Box } from "spectacle";
import { Mermaid } from "../components/Mermaid";
import { Radial } from "../components/Radial";
import { ComparisonPanel } from "../components/ComparisonPanel";
import { Spectrum } from "../components/Spectrum";
import { colors } from "../theme";

export function ThreeLayersSlide() {
  const layer = (
    title: string,
    body: string,
    accent: string,
    note?: string,
    highlighted = false,
  ) => (
    <div
      style={{
        border: `2px solid ${highlighted ? accent : colors.border}`,
        borderLeft: `6px solid ${accent}`,
        background: highlighted ? `${colors.surface}` : colors.tertiary,
        padding: "14px 20px",
        borderRadius: 6,
        fontFamily: colors.sans,
        boxShadow: highlighted ? `0 0 0 1px ${accent}33` : undefined,
        opacity: note?.includes("out of scope") ? 0.55 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: accent }}>{title}</div>
        {note && (
          <div style={{ fontSize: 13, color: highlighted ? colors.quinary : colors.secondary, fontWeight: 600 }}>
            {note}
          </div>
        )}
      </div>
      <div style={{ fontSize: 15, color: colors.primary, marginTop: 4 }}>{body}</div>
    </div>
  );

  return (
    <Slide>
      <Heading fontSize="42px">The three layers</Heading>
      <Text fontSize="18px" color="secondary" margin="-8px 0 12px">
        A model is intelligence. A harness is the runtime that turns intelligence into an
        agent. Agentic engineering is the practice of using those agents to build software.
      </Text>
      <Box>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {layer(
            "Agentic engineering",
            "The practice of using agents to build products, software, and workflows.",
            colors.quaternary,
          )}
          {layer(
            "Harness engineering",
            "The runtime around a model — control flow, memory, tools, sandbox, guardrails, observability, evals, performance.",
            colors.quinary,
            "← this repo",
            true,
          )}
          {layer(
            "Model development",
            "Training and fine-tuning the model itself.",
            colors.workflow,
            "out of scope",
          )}
        </div>
      </Box>
    </Slide>
  );
}

export function HarnessEngineeringSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">What is harness engineering?</Heading>
      <Text fontSize="18px" color="quaternary" margin="-10px 0 6px">
        <strong>Agent = Model + Harness.</strong> The harness is every piece of code,
        configuration, and execution logic that isn't the model.
      </Text>
      <Radial
        center="Harness"
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
      <Text fontSize="15px" color="secondary" margin="-8px 0 4px">
        Both shapes describe the harness's control flow. Workflows hard-code the path;
        agents let the model pick it.
      </Text>
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
        This curriculum builds harnesses for purist agents; workflows are out of scope.
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
