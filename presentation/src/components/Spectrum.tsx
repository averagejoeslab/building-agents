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
  const width = 1200;
  const height = 240;
  const lineY = 130;
  const margin = 150;
  const lineLength = width - margin * 2;
  const xAt = (p: number) => margin + p * lineLength;

  // Smart anchoring so leftmost/rightmost labels don't overflow.
  const anchorFor = (p: number): "start" | "middle" | "end" => {
    if (p <= 0.1) return "start";
    if (p >= 0.7) return "end";
    return "middle";
  };

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxHeight: "55vh" }}>
      {/* Highlight band (drawn behind the line) */}
      {highlightFrom !== undefined && highlightTo !== undefined && (
        <g>
          <rect
            x={xAt(highlightFrom)}
            y={lineY - 28}
            width={xAt(highlightTo) - xAt(highlightFrom)}
            height={56}
            fill={colors.quinary}
            opacity={0.18}
            rx="6"
          />
          {highlightLabel && (
            <text
              x={(xAt(highlightFrom) + xAt(highlightTo)) / 2}
              y={lineY - 42}
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

      {/* Main line */}
      <line
        x1={margin}
        y1={lineY}
        x2={width - margin}
        y2={lineY}
        stroke={colors.border}
        strokeWidth="3"
      />

      {/* Edge labels — sit in the side margins, anchored toward the line */}
      <text
        x={margin - 18}
        y={lineY + 7}
        textAnchor="end"
        fontSize="22"
        fill={colors.workflow}
        fontWeight="700"
        fontFamily={colors.sans}
      >
        {leftLabel}
      </text>
      <text
        x={width - margin + 18}
        y={lineY + 7}
        textAnchor="start"
        fontSize="22"
        fill={colors.quinary}
        fontWeight="700"
        fontFamily={colors.sans}
      >
        {rightLabel}
      </text>

      {/* Points (drawn on top of the line and band) */}
      {points.map((p, i) => {
        const x = xAt(p.position);
        const color = p.color ?? colors.primary;
        const anchor = anchorFor(p.position);
        return (
          <g key={i}>
            <circle cx={x} cy={lineY} r="9" fill={color} stroke={colors.surface} strokeWidth="2" />
            <text
              x={x}
              y={lineY + 32}
              textAnchor={anchor}
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
                y={lineY + 52}
                textAnchor={anchor}
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
