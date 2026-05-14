import { Slide, Heading, Text, UnorderedList, ListItem, CodePane, Notes } from "spectacle";
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
      <Heading fontSize="38px">Stateless API, stateful loop</Heading>
      <Text fontSize="24px">
        The Messages API is <strong>stateless</strong>. The server doesn't remember
        anything between calls.
      </Text>
      <Text fontSize="24px" margin="32px 0 0">
        So the <em>program</em> keeps the state. Every turn, the full <code>messages</code>{" "}
        list goes back over the wire.
      </Text>
      <Notes>
        The conversation lives in your variable — no server-side session needed.
      </Notes>
    </Slide>
  );
}

export function TieToEnvironmentSlide() {
  return (
    <Slide>
      <Heading fontSize="38px">Tie the loop to an environment</Heading>
      <Text fontSize="22px">
        A loop in a vacuum is useless. It has to be <strong>bootstrapped into an
        environment</strong> — just as a person is bootstrapped into a body and a world.
      </Text>
      <Text fontSize="22px" margin="24px 0 0" color="secondary">
        The environment is the agent's world.
      </Text>
      <UnorderedList fontSize="20px">
        <ListItem>
          <strong>Terminal</strong> — stdin / stdout. Our pick.
        </ListItem>
        <ListItem>
          <strong>Web socket</strong> — browser in, streaming SSE out.
        </ListItem>
        <ListItem>
          <strong>Slack channel</strong> — slash command in, thread reply out.
        </ListItem>
        <ListItem>
          <strong>Gameboy emulator</strong> — button presses in, screen out. Give it a
          "press button" tool and the agent eventually lives and plays in the console.
        </ListItem>
        <ListItem>
          <strong>Spreadsheet cell</strong> — formula args in, cell value out.
        </ListItem>
      </UnorderedList>
    </Slide>
  );
}

export function ChatbotCodeSlide() {
  return (
    <Slide>
      <Heading fontSize="32px">The chatbot — stateless_chatbot.py</Heading>
      <CodePane language="python" showLineNumbers={false}>
        {chatbotCode}
      </CodePane>
      <Text fontSize="18px" color="secondary" margin="16px 0 0">
        Async streaming, REPL-shaped, history in a single in-process list.
      </Text>
    </Slide>
  );
}

export function ChatbotIsntAgentSlide() {
  return (
    <Slide>
      <Heading fontSize="40px">Why this isn't an agent yet</Heading>
      <Text fontSize="26px">
        The chatbot can talk forever, but it can't <em>do</em> anything. It can describe
        how to read a file, propose what a config change might look like — but it cannot
        read, run, or write.
      </Text>
      <Text fontSize="24px" color="quinary" margin="40px 0 0">
        To act, the model needs <strong>tools</strong>. That's the next module.
      </Text>
    </Slide>
  );
}
