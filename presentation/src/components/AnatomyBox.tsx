import { colors } from "../theme";

export type AnatomyField = {
  name: string;
  type?: string;
  description?: string;
};

type Props = {
  title: string;
  subtitle?: string;
  fields: AnatomyField[];
  accent?: string;
};

export function AnatomyBox({ title, subtitle, fields, accent = colors.quaternary }: Props) {
  return (
    <div
      style={{
        border: `2px solid ${accent}`,
        borderRadius: 8,
        padding: 18,
        background: colors.surface,
        fontFamily: colors.sans,
        minWidth: 360,
      }}
    >
      <div
        style={{
          fontFamily: colors.mono,
          fontSize: 18,
          fontWeight: 700,
          color: accent,
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      {subtitle && (
        <div style={{ fontSize: 13, color: colors.secondary, marginBottom: 14 }}>{subtitle}</div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {fields.map((field, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "150px 90px 1fr", gap: 12, fontSize: 14 }}>
            <div style={{ fontFamily: colors.mono, color: colors.primary, fontWeight: 600 }}>
              {field.name}
            </div>
            <div style={{ fontFamily: colors.mono, color: colors.workflow }}>
              {field.type ?? ""}
            </div>
            <div style={{ color: colors.secondary }}>{field.description ?? ""}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
