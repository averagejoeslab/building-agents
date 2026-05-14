import { colors } from "../theme";

export type SpectrumPoint = {
  position: number;  // 0-1 (left-to-right)
  label: string;
  sublabel?: string;
  color?: string;
};

type Props = {
  leftLabel: string;
  rightLabel: string;
  points: SpectrumPoint[];
  highlightFrom?: number;  // 0-1
  highlightTo?: number;    // 0-1
  highlightLabel?: string;
};

export function Spectrum({
  leftLabel,
  rightLabel,
  points,
  highlightFrom,
  highlightTo,
  highlightLabel,
}: Props) {
  const width = 1000;
  const height = 220;
  const lineY = 130;
  const margin = 80;
  const lineLength = width - margin * 2;
  const xAt = (p: number) => margin + p * lineLength;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxHeight: "40vh" }}>
      {/* highlighted range */}
      {highlightFrom !== undefined && highlightTo !== undefined && (
        <g>
          <rect
            x={xAt(highlightFrom)}
            y={lineY - 30}
            width={xAt(highlightTo) - xAt(highlightFrom)}
            height={60}
            fill={colors.quinary}
            opacity={0.18}
            rx="6"
          />
          {highlightLabel && (
            <text
              x={(xAt(highlightFrom) + xAt(highlightTo)) / 2}
              y={lineY - 40}
              textAnchor="middle"
              fontSize="16"
              fill={colors.quinary}
              fontWeight="700"
              fontFamily={colors.sans}
            >
              {highlightLabel}
            </text>
          )}
        </g>
      )}

      {/* main line */}
      <line x1={margin} y1={lineY} x2={width - margin} y2={lineY} stroke={colors.border} strokeWidth="3" />
      <polygon points={`${margin - 6},${lineY} ${margin + 6},${lineY - 8} ${margin + 6},${lineY + 8}`} fill={colors.border} />
      <polygon points={`${width - margin + 6},${lineY} ${width - margin - 6},${lineY - 8} ${width - margin - 6},${lineY + 8}`} fill={colors.border} />

      {/* edge labels */}
      <text x={margin - 12} y={lineY + 6} textAnchor="end" fontSize="20" fill={colors.workflow} fontWeight="700" fontFamily={colors.sans}>
        {leftLabel}
      </text>
      <text x={width - margin + 12} y={lineY + 6} textAnchor="start" fontSize="20" fill={colors.quinary} fontWeight="700" fontFamily={colors.sans}>
        {rightLabel}
      </text>

      {/* points */}
      {points.map((p, i) => {
        const x = xAt(p.position);
        const color = p.color ?? colors.primary;
        return (
          <g key={i}>
            <circle cx={x} cy={lineY} r="9" fill={color} stroke={colors.surface} strokeWidth="2" />
            <text
              x={x}
              y={lineY + 30}
              textAnchor="middle"
              fontSize="15"
              fill={colors.primary}
              fontWeight="600"
              fontFamily={colors.sans}
            >
              {p.label}
            </text>
            {p.sublabel && (
              <text
                x={x}
                y={lineY + 50}
                textAnchor="middle"
                fontSize="12"
                fill={colors.secondary}
                fontFamily={colors.sans}
              >
                {p.sublabel}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
