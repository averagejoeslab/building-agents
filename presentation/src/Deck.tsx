import { Deck as SpectacleDeck } from "spectacle";
import { theme } from "./theme";

import { CoverSlide } from "./slides/00-cover";
import {
  ThreeLayersSlide,
  HarnessEngineeringSlide,
  WhatAreAgenticSystemsSlide,
  WorkflowsVsAgentsSlide,
  AverageJoesStanceSlide,
} from "./slides/01-orientation";
import {
  ModuleOneTitleSlide,
  ThreeComponentsSlide,
  TAOLoopSlide,
  ToolShapeSlide,
  ConcreteTraceSlide,
} from "./slides/02-what-is-an-agent";
import {
  ModuleTwoTitleSlide,
  MessagesAPISlide,
  SyncCallSlide,
  StreamingMattersSlide,
  AsyncStreamingSlide,
  StreamingForAgentsSlide,
} from "./slides/03-llm-call";
import {
  ModuleThreeTitleSlide,
  StatelessStatefulLoopSlide,
  TieToEnvironmentSlide,
  ChatbotCodeSlide,
  ChatbotIsntAgentSlide,
} from "./slides/04-add-a-loop";
import { WhatsNextSlide, ClosingSlide } from "./slides/05-closing";

export function Deck() {
  return (
    <SpectacleDeck theme={theme}>
      <CoverSlide />

      {/* Orientation */}
      <ThreeLayersSlide />
      <HarnessEngineeringSlide />
      <WhatAreAgenticSystemsSlide />
      <WorkflowsVsAgentsSlide />
      <AverageJoesStanceSlide />

      {/* Module 1 — What is an agent? */}
      <ModuleOneTitleSlide />
      <ThreeComponentsSlide />
      <TAOLoopSlide />
      <ToolShapeSlide />
      <ConcreteTraceSlide />

      {/* Module 2 — An LLM call */}
      <ModuleTwoTitleSlide />
      <MessagesAPISlide />
      <SyncCallSlide />
      <StreamingMattersSlide />
      <AsyncStreamingSlide />
      <StreamingForAgentsSlide />

      {/* Module 3 — Add a loop */}
      <ModuleThreeTitleSlide />
      <StatelessStatefulLoopSlide />
      <TieToEnvironmentSlide />
      <ChatbotCodeSlide />
      <ChatbotIsntAgentSlide />

      {/* Wrap */}
      <WhatsNextSlide />
      <ClosingSlide />
    </SpectacleDeck>
  );
}
