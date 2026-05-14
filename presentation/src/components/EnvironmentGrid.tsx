import { colors } from "../theme";

export type EnvCard = {
  title: string;
  glyph: string;          // emoji or short text glyph
  inLabel: string;
  outLabel: string;
  accent?: string;
};

type Props = {
  cards: EnvCard[];
};

export function EnvironmentGrid({ cards }: Props) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 18,
        width: "100%",
        marginTop: 12,
      }}
    >
      {cards.map((c, i) => (
        <Card key={i} {...c} />
      ))}
    </div>
  );
}

function Card({ title, glyph, inLabel, outLabel, accent = colors.quaternary }: EnvCard) {
  return (
    <div
      style={{
        border: `2px solid ${colors.border}`,
        borderLeft: `4px solid ${accent}`,
        borderRadius: 8,
        padding: 16,
        background: colors.surface,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        fontFamily: colors.sans,
      }}
    >
      <div style={{ fontSize: 48, lineHeight: 1, textAlign: "center" }}>{glyph}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: accent, textAlign: "center" }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: colors.secondary }}>
        <div>
          <span style={{ color: colors.quinary, fontWeight: 700 }}>↓ in:&nbsp;</span>{inLabel}
        </div>
        <div>
          <span style={{ color: colors.quaternary, fontWeight: 700 }}>↑ out:&nbsp;</span>{outLabel}
        </div>
      </div>
    </div>
  );
}
