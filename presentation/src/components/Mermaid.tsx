import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

let initialized = false;

function initMermaid() {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    securityLevel: "loose",
    themeVariables: {
      darkMode: true,
      background: "#0d1117",
      primaryColor: "#161b22",
      primaryTextColor: "#e6edf3",
      primaryBorderColor: "#30363d",
      lineColor: "#7d8590",
      secondaryColor: "#1f6feb",
      tertiaryColor: "#21262d",
      fontFamily: "Inter, sans-serif",
    },
  });
  initialized = true;
}

let counter = 0;

type Props = {
  children: string;
};

export function Mermaid({ children }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    initMermaid();
    const id = `mermaid-${++counter}`;
    mermaid
      .render(id, children.trim())
      .then(({ svg }) => setSvg(svg))
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.error("mermaid render failed", err);
        setSvg(`<pre>${String(err)}</pre>`);
      });
  }, [children]);

  return (
    <div
      ref={containerRef}
      style={{ display: "flex", justifyContent: "center", width: "100%" }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
