import { ReactNode } from "react";
import { CodePane } from "spectacle";

type Props = {
  language: string;
  showLineNumbers?: boolean;
  fontSize?: string | number;
  children: string;
};

/**
 * Wraps Spectacle's CodePane so we can shrink the code-block font for
 * dense or long files. CodePane itself has no fontSize prop; the wrapper
 * uses CSS cascade — vsDark theme only sets color/background on the pre,
 * so font-size inherits through to the tokens.
 */
export function Code({ language, showLineNumbers, fontSize = "14px", children }: Props): ReactNode {
  return (
    <div style={{ fontSize }}>
      <CodePane language={language} showLineNumbers={showLineNumbers}>
        {children}
      </CodePane>
    </div>
  );
}
