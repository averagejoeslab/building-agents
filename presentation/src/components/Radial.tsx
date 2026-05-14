import { colors } from "../theme";

export type Spoke = {
  label: string;
  group?: 0 | 1 | 2;  // 0=foundational, 1=behavioral, 2=operational
};

type Props = {
  center: string;
  centerSub?: string;
  spokes: Spoke[];
  legend?: Array<{ label: string; color: string }>;
};

export function Radial({ center, centerSub, spokes, legend }: Props) {
  const size = 640;
  const cx = size / 2;
  const cy = size / 2;
  const r = 230;
  const nodeR = 54;

  const groupColor = (g?: number) =>
    g === 1 ? colors.quinary : g === 2 ? colors.workflow : colors.quaternary;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxHeight: "65vh" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={colors.border} strokeDasharray="3 6" />
        <circle cx={cx} cy={cy} r="84" fill={colors.quaternary} />
        <text x={cx} y={cy - 6} textAnchor="middle" fill="white" fontSize="18" fontWeight="700" fontFamily={colors.sans}>
          {center}
        </text>
        {centerSub && (
          <text x={cx} y={cy + 18} textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize="13" fontFamily={colors.sans}>
            {centerSub}
          </text>
        )}

        {spokes.map((spoke, i) => {
          const angle = (i / spokes.length) * 2 * Math.PI - Math.PI / 2;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const color = groupColor(spoke.group);
          return (
            <g key={i}>
              <line x1={cx} y1={cy} x2={x} y2={y} stroke={colors.border} />
              <circle cx={x} cy={y} r={nodeR} fill={colors.surface} stroke={color} strokeWidth="2.5" />
              <text x={x} y={y} textAnchor="middle" alignmentBaseline="central" fill={colors.primary} fontSize="13" fontFamily={colors.sans} fontWeight="600">
                {spoke.label}
              </text>
            </g>
          );
        })}
      </svg>

      {legend && (
        <div style={{ display: "flex", gap: 24, fontFamily: colors.sans, fontSize: 14, color: colors.secondary }}>
          {legend.map((l, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ display: "inline-block", width: 14, height: 14, borderRadius: 4, background: l.color }} />
              {l.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
