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

  const positions = spokes.map((spoke, i) => {
    const angle = (i / spokes.length) * 2 * Math.PI - Math.PI / 2;
    return {
      spoke,
      angle,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });

  const centerR = 84;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxHeight: "65vh" }}>
        {/* Layer 1: dashed outer ring (behind everything) */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={colors.border} strokeDasharray="3 6" />

        {/* Layer 2: spoke lines — start at the center node's edge, end at the spoke's edge */}
        {positions.map(({ angle, x, y }, i) => {
          const startX = cx + centerR * Math.cos(angle);
          const startY = cy + centerR * Math.sin(angle);
          const endX = x - nodeR * Math.cos(angle);
          const endY = y - nodeR * Math.sin(angle);
          return (
            <line
              key={`line-${i}`}
              x1={startX}
              y1={startY}
              x2={endX}
              y2={endY}
              stroke={colors.border}
            />
          );
        })}

        {/* Layer 3: center node (on top of lines) */}
        <circle cx={cx} cy={cy} r={centerR} fill={colors.quaternary} />
        <text x={cx} y={cy - 6} textAnchor="middle" fill="white" fontSize="18" fontWeight="700" fontFamily={colors.sans}>
          {center}
        </text>
        {centerSub && (
          <text x={cx} y={cy + 18} textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize="13" fontFamily={colors.sans}>
            {centerSub}
          </text>
        )}

        {/* Layer 4: spoke nodes (on top of lines, like the center) */}
        {positions.map(({ spoke, x, y }, i) => {
          const color = groupColor(spoke.group);
          return (
            <g key={`spoke-${i}`}>
              <circle cx={x} cy={y} r={nodeR} fill={colors.surface} stroke={color} strokeWidth="2.5" />
              <text
                x={x}
                y={y}
                textAnchor="middle"
                alignmentBaseline="central"
                fill={colors.primary}
                fontSize="13"
                fontFamily={colors.sans}
                fontWeight="600"
              >
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
