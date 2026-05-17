import { Slide, Heading, Text, FlexBox } from "spectacle";

export function CoverSlide() {
  return (
    <Slide>
      <FlexBox height="100%" flexDirection="column" justifyContent="center">
        <Heading fontSize="96px" margin="0">
          agenteng
        </Heading>
        <Text fontSize="28px" color="secondary" margin="24px 0 0">
          A framework-free, code-first curriculum for{" "}
          <span style={{ color: "#3fb950" }}>harness engineering</span>.
        </Text>
        <Text fontSize="18px" color="secondary" margin="12px 0 0">
          Build the runtime that turns a model into an autonomous coding agent.
        </Text>
        <Text fontSize="20px" color="secondary" margin="60px 0 0">
          github.com/averagejoeslab/agenteng
        </Text>
      </FlexBox>
    </Slide>
  );
}
