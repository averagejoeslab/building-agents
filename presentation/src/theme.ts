export const colors = {
  primary: "#e6edf3",       // body text
  secondary: "#7d8590",     // muted text
  tertiary: "#0d1117",      // background
  surface: "#161b22",       // card background
  border: "#30363d",        // borders
  quaternary: "#58a6ff",    // blue accent
  quinary: "#3fb950",       // green accent — "agent / model decides"
  workflow: "#f0883e",      // orange accent — "code decides"
  danger: "#f85149",        // red — "can't / blocked"
  mono: '"JetBrains Mono", "SF Mono", Consolas, Menlo, monospace',
  sans: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
};

export const theme = {
  colors: {
    primary: colors.primary,
    secondary: colors.secondary,
    tertiary: colors.tertiary,
    quaternary: colors.quaternary,
    quinary: colors.quinary,
  },
  fonts: {
    header: colors.sans,
    text: colors.sans,
    monospace: colors.mono,
  },
  fontSizes: {
    h1: "60px",
    h2: "44px",
    h3: "30px",
    text: "24px",
    monospace: "20px",
  },
};
