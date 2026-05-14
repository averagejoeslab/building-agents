import { Slide, Heading, Text, Notes } from "spectacle";
import { StateSplit } from "../components/StateSplit";
import { EnvironmentGrid } from "../components/EnvironmentGrid";
import { CapabilityMatrix } from "../components/CapabilityMatrix";
import { Code } from "../components/Code";
import { colors } from "../theme";
import chatbotCode from "@examples/stateless_chatbot.py?raw";

export function ModuleThreeTitleSlide() {
  return (
    <Slide>
      <Heading fontSize="32px" color="secondary">
        Module 3
      </Heading>
      <Heading fontSize="64px">Add a loop → a chatbot</Heading>
      <Text fontSize="24px" color="quaternary" margin="32px 0 0">
        Not an agent yet — text only, no tools. Tools come next.
      </Text>
    </Slide>
  );
}

export function StatelessStatefulLoopSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">Stateless API, stateful loop</Heading>
      <Text fontSize="17px" color="secondary" margin="-8px 0 8px">
        The Messages API forgets every call. Your program is the only place the
        conversation lives.
      </Text>
      <StateSplit />
      <Notes>
        This is the trick that makes multi-turn conversation possible without any
        server-side session — the conversation lives in your variable.
      </Notes>
    </Slide>
  );
}

export function TieToEnvironmentSlide() {
  return (
    <Slide>
      <Heading fontSize="36px">Tie the loop to an environment</Heading>
      <Text fontSize="16px" color="secondary" margin="-8px 0 6px">
        A loop in a vacuum is useless. Just as a person is bootstrapped into a body
        and a world, a loop has to be bootstrapped into an environment.{" "}
        <strong style={{ color: colors.quinary }}>The environment is the agent's world.</strong>
      </Text>
      <EnvironmentGrid
        cards={[
          {
            title: "Terminal",
            glyph: "❯_",
            inLabel: "stdin (text lines)",
            outLabel: "stdout (text)",
            accent: colors.quinary,
          },
          {
            title: "Web socket",
            glyph: "🌐",
            inLabel: "browser messages",
            outLabel: "Server-Sent Events",
            accent: colors.quaternary,
          },
          {
            title: "Slack",
            glyph: "💬",
            inLabel: "slash command",
            outLabel: "thread reply",
            accent: colors.quaternary,
          },
          {
            title: "Gameboy emulator",
            glyph: "🎮",
            inLabel: "button presses + screen",
            outLabel: '"press button" tool',
            accent: colors.workflow,
          },
          {
            title: "Minecraft server",
            glyph: "🧱",
            inLabel: "chat & game events",
            outLabel: "block actions",
            accent: colors.workflow,
          },
          {
            title: "Spreadsheet",
            glyph: "▦",
            inLabel: "=AGENT(args)",
            outLabel: "cell value",
            accent: colors.quaternary,
          },
        ]}
      />
      <Text fontSize="14px" color="secondary" margin="14px 0 0" textAlign="center">
        Same loop. Totally different agents. We pick <strong style={{ color: colors.quinary }}>terminal</strong> because it has the least ceremony.
      </Text>
    </Slide>
  );
}

export function ChatbotCodeSlide() {
  return (
    <Slide>
      <Heading fontSize="28px">The chatbot — stateless_chatbot.py</Heading>
      <Code language="python" fontSize={13}>{chatbotCode}</Code>
      <Text fontSize="14px" color="secondary" margin="10px 0 0">
        Async streaming, REPL-shaped, history in a single in-process list.
      </Text>
    </Slide>
  );
}

export function ChatbotIsntAgentSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">Why this isn't an agent yet</Heading>
      <Text fontSize="18px" color="secondary" margin="-8px 0 8px">
        The chatbot can talk forever, but it can't <em>do</em> anything.
      </Text>
      <CapabilityMatrix
        rows={[
          { capability: "Read a file", describe: true, act: false },
          { capability: "Run a shell command", describe: true, act: false },
          { capability: "Edit a config", describe: true, act: false },
          { capability: "Send a request", describe: true, act: false },
        ]}
      />
      <Text fontSize="20px" margin="20px 0 0" textAlign="center" color="quinary">
        To act, the model needs <strong>tools</strong>. That's the next module.
      </Text>
    </Slide>
  );
}
