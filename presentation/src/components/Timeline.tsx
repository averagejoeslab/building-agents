import { colors } from "../theme";

type TimelineEvent = {
  at: number;
  label?: string;
  emphasis?: boolean;
};

type ShadedRange = {
  from: number;
  to: number;
  label?: string;
  color?: string;
};

export type TimelineTrack = {
  label: string;
  sublabel?: string;
  color: string;
  events?: TimelineEvent[];
  shaded?: ShadedRange[];
};

type Props = {
  tracks: TimelineTrack[];
  duration: number;
  units?: string;
  highlightLabel?: string;
};

export function Timeline({ tracks, duration, units = "s", highlightLabel }: Props) {
  const width = 1000;
  const labelWidth = 220;
  const margin = 30;
  const barStart = labelWidth;
  const barWidth = width - barStart - margin;
  const trackHeight = 80;
  const barHeight = 36;
  const totalHeight = tracks.length * trackHeight + 80;

  const xAt = (t: number) => barStart + (t / duration) * barWidth;

  return (
    <svg viewBox={`0 0 ${width} ${totalHeight}`} width="100%" style={{ maxHeight: "60vh" }}>
      {tracks.map((track, i) => {
        const y = 30 + i * trackHeight;
        return (
          <g key={i}>
            <text x={labelWidth - 16} y={y + 18} textAnchor="end" fontSize="20" fontWeight="700" fill={colors.primary} fontFamily={colors.sans}>
              {track.label}
            </text>
            {track.sublabel && (
              <text x={labelWidth - 16} y={y + 38} textAnchor="end" fontSize="13" fill={colors.secondary} fontFamily={colors.sans}>
                {track.sublabel}
              </text>
            )}
            <rect x={barStart} y={y} width={barWidth} height={barHeight} fill={colors.surface} stroke={colors.border} rx="4" />
            {track.shaded?.map((range, j) => (
              <g key={`shaded-${j}`}>
                <rect
                  x={xAt(range.from)}
                  y={y}
                  width={xAt(range.to) - xAt(range.from)}
                  height={barHeight}
                  fill={range.color ?? track.color}
                  opacity={0.35}
                />
                {range.label && (
                  <text
                    x={(xAt(range.from) + xAt(range.to)) / 2}
                    y={y + 23}
                    textAnchor="middle"
                    fontSize="14"
                    fill={colors.primary}
                    fontFamily={colors.sans}
                  >
                    {range.label}
                  </text>
                )}
              </g>
            ))}
            {track.events?.map((event, j) => (
              <g key={`event-${j}`}>
                <line
                  x1={xAt(event.at)}
                  x2={xAt(event.at)}
                  y1={y - 4}
                  y2={y + barHeight + 4}
                  stroke={track.color}
                  strokeWidth={event.emphasis ? 3 : 2}
                />
                {event.label && (
                  <text
                    x={xAt(event.at)}
                    y={y - 10}
                    textAnchor="middle"
                    fontSize="13"
                    fill={track.color}
                    fontWeight={event.emphasis ? 700 : 500}
                    fontFamily={colors.sans}
                  >
                    {event.label}
                  </text>
                )}
              </g>
            ))}
          </g>
        );
      })}
      <g>
        {Array.from({ length: 6 }).map((_, i) => {
          const x = barStart + (i / 5) * barWidth;
          const t = (i / 5) * duration;
          return (
            <g key={i}>
              <line x1={x} x2={x} y1={tracks.length * trackHeight + 18} y2={tracks.length * trackHeight + 26} stroke={colors.secondary} />
              <text x={x} y={tracks.length * trackHeight + 44} textAnchor="middle" fontSize="13" fill={colors.secondary} fontFamily={colors.sans}>
                {t.toFixed(1)}{units}
              </text>
            </g>
          );
        })}
      </g>
      {highlightLabel && (
        <text
          x={width / 2}
          y={totalHeight - 6}
          textAnchor="middle"
          fontSize="15"
          fill={colors.quinary}
          fontWeight="700"
          fontFamily={colors.sans}
        >
          {highlightLabel}
        </text>
      )}
    </svg>
  );
}
