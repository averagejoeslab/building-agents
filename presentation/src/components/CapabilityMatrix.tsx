import { colors } from "../theme";

export type CapabilityRow = {
  capability: string;
  describe: boolean;
  act: boolean;
};

type Props = {
  rows: CapabilityRow[];
  describeLabel?: string;
  actLabel?: string;
};

export function CapabilityMatrix({ rows, describeLabel = "Can describe", actLabel = "Can do" }: Props) {
  return (
    <div style={{ fontFamily: colors.sans, width: "90%", margin: "0 auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ padding: 14, textAlign: "left", color: colors.secondary, fontSize: 18, borderBottom: `2px solid ${colors.border}` }}></th>
            <th style={{ padding: 14, color: colors.quaternary, fontSize: 20, fontWeight: 700, borderBottom: `2px solid ${colors.border}`, textAlign: "center" }}>
              {describeLabel}
            </th>
            <th style={{ padding: 14, color: colors.danger, fontSize: 20, fontWeight: 700, borderBottom: `2px solid ${colors.border}`, textAlign: "center" }}>
              {actLabel}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
              <td style={{ padding: 14, fontSize: 22, color: colors.primary }}>{row.capability}</td>
              <td style={{ padding: 14, fontSize: 28, fontWeight: 700, textAlign: "center", color: row.describe ? colors.quinary : colors.secondary }}>
                {row.describe ? "✓" : "—"}
              </td>
              <td style={{ padding: 14, fontSize: 28, fontWeight: 700, textAlign: "center", color: row.act ? colors.quinary : colors.danger }}>
                {row.act ? "✓" : "✗"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
