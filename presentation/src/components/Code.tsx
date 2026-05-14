import { ReactNode } from "react";
import { CodePane } from "spectacle";
import "./code.css";

type Props = {
  language: string;
  /** Defaults to `false` — Spectacle's CodePane defaults to true. */
  showLineNumbers?: boolean;
  /**
   * Pixel font size. Maps to a CSS class with `!important` because
   * Spectacle writes the monospace size inline from the theme and a parent
   * font-size won't beat an inline value.
   */
  fontSize?: 12 | 13 | 14 | 15 | 16 | 18;
  children: string;
};

export function Code({
  language,
  showLineNumbers = false,
  fontSize = 14,
  children,
}: Props): ReactNode {
  return (
    <div className={`code-${fontSize}`}>
      <CodePane language={language} showLineNumbers={showLineNumbers}>
        {children}
      </CodePane>
    </div>
  );
}
