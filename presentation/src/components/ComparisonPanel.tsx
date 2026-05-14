import { ReactNode } from "react";
import { colors } from "../theme";

export type ComparisonSide = {
  title: string;
  subtitle?: string;
  accent?: string;
  content: ReactNode;
};

type Props = {
  left: ComparisonSide;
  right: ComparisonSide;
};

export function ComparisonPanel({ left, right }: Props) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, width: "100%" }}>
      {[left, right].map((side, i) => (
        <div
          key={i}
          style={{
            border: `2px solid ${side.accent ?? colors.border}`,
            borderRadius: 8,
            padding: 20,
            background: colors.surface,
            fontFamily: colors.sans,
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: side.accent ?? colors.primary }}>
              {side.title}
            </div>
            {side.subtitle && (
              <div style={{ fontSize: 14, color: colors.secondary, marginTop: 4 }}>{side.subtitle}</div>
            )}
          </div>
          <div style={{ color: colors.primary, fontSize: 16 }}>{side.content}</div>
        </div>
      ))}
    </div>
  );
}
