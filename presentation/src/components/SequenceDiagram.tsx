import { colors } from "../theme";

type Lane = { label: string };

export type SeqEvent = {
  from: number;        // lane index
  to: number;          // lane index
  label: string;
  kind?: "call" | "stream" | "return" | "note";
};

type Props = {
  lanes: Lane[];
  events: SeqEvent[];
};

export function SequenceDiagram({ lanes, events }: Props) {
  const width = 1000;
  const headerHeight = 50;
  const eventSpacing = 56;
  const sideMargin = 80;
  const laneStep = (width - sideMargin * 2) / Math.max(1, lanes.length - 1);
  const height = headerHeight + events.length * eventSpacing + 60;

  const laneX = (i: number) => sideMargin + i * laneStep;

  const colorFor = (kind?: SeqEvent["kind"]) => {
    switch (kind) {
      case "stream":
        return colors.quinary;
      case "return":
        return colors.secondary;
      case "note":
        return colors.workflow;
      default:
        return colors.quaternary;
    }
  };

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ maxHeight: "65vh" }}>
      <defs>
        <marker id="arr-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill={colors.quaternary} />
        </marker>
        <marker id="arr-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill={colors.quinary} />
        </marker>
        <marker id="arr-gray" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill={colors.secondary} />
        </marker>
      </defs>

      {/* Lane headers and vertical lines */}
      {lanes.map((lane, i) => {
        const x = laneX(i);
        return (
          <g key={i}>
            <rect x={x - 100} y={5} width={200} height={40} fill={colors.surface} stroke={colors.border} rx="6" />
            <text x={x} y={31} textAnchor="middle" fontSize="18" fill={colors.primary} fontWeight="700" fontFamily={colors.sans}>
              {lane.label}
            </text>
            <line x1={x} y1={headerHeight} x2={x} y2={height - 20} stroke={colors.border} strokeDasharray="4 6" />
          </g>
        );
      })}

      {/* Events */}
      {events.map((event, i) => {
        const y = headerHeight + 30 + i * eventSpacing;
        const x1 = laneX(event.from);
        const x2 = laneX(event.to);
        const stroke = colorFor(event.kind);
        const isReturn = event.kind === "return";
        const isStream = event.kind === "stream";
        const dashArray = isReturn ? "8 4" : isStream ? "6 3" : undefined;
        const markerId = isReturn ? "arr-gray" : isStream ? "arr-green" : "arr-blue";

        if (event.kind === "note") {
          return (
            <g key={i}>
              <rect
                x={Math.min(x1, x2) - 20}
                y={y - 14}
                width={Math.abs(x2 - x1) + 40}
                height={28}
                fill={colors.workflow}
                opacity={0.15}
                stroke={colors.workflow}
                rx="4"
              />
              <text
                x={(x1 + x2) / 2}
                y={y + 4}
                textAnchor="middle"
                fontSize="14"
                fill={colors.workflow}
                fontWeight="700"
                fontFamily={colors.sans}
              >
                {event.label}
              </text>
            </g>
          );
        }

        if (event.from === event.to) {
          // self-loop
          const dx = 40;
          return (
            <g key={i}>
              <path
                d={`M ${x1} ${y} h ${dx} v ${20} h -${dx}`}
                fill="none"
                stroke={stroke}
                strokeWidth="2"
                strokeDasharray={dashArray}
                markerEnd={`url(#${markerId})`}
              />
              <text x={x1 + dx + 8} y={y + 14} fontSize="14" fill={stroke} fontFamily={colors.sans}>
                {event.label}
              </text>
            </g>
          );
        }

        return (
          <g key={i}>
            <line
              x1={x1}
              y1={y}
              x2={x2}
              y2={y}
              stroke={stroke}
              strokeWidth="2"
              strokeDasharray={dashArray}
              markerEnd={`url(#${markerId})`}
            />
            <text
              x={(x1 + x2) / 2}
              y={y - 8}
              textAnchor="middle"
              fontSize="14"
              fill={stroke}
              fontWeight="600"
              fontFamily={colors.sans}
            >
              {event.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
