import { Slide, Heading, Text, FlexBox } from "spectacle";

export function CoverSlide() {
  return (
    <Slide>
      <FlexBox height="100%" flexDirection="column" justifyContent="center">
        <Heading fontSize="96px" margin="0">
          agenteng
        </Heading>
        <Text fontSize="32px" color="secondary" margin="24px 0 0">
          A framework-free take on{" "}
          <span style={{ color: "#58a6ff" }}>agentic engineering</span>.
        </Text>
        <Text fontSize="20px" color="secondary" margin="60px 0 0">
          github.com/averagejoeslab/agenteng
        </Text>
      </FlexBox>
    </Slide>
  );
}
