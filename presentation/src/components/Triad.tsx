import { colors } from "../theme";

type TriadNode = { label: string; sublabel?: string };

type Props = {
  nodes: [TriadNode, TriadNode, TriadNode];
  center: string;
  centerSub?: string;
};

export function Triad({ nodes, center, centerSub }: Props) {
  const size = 560;
  const cx = size / 2;
  const cy = size / 2 + 20;
  const r = 200;
  const nodeR = 70;
  const centerR = 80;

  const angles = [-Math.PI / 2, Math.PI / 2 + Math.PI / 3, Math.PI / 2 - Math.PI / 3];
  const positions = angles.map((angle) => ({
    angle,
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  }));

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxHeight: "70vh" }}>
      {/* Layer 1: spokes from center → each component (behind everything) */}
      {positions.map(({ angle, x, y }, i) => {
        const startX = cx + centerR * Math.cos(angle);
        const startY = cy + centerR * Math.sin(angle);
        const endX = x - nodeR * Math.cos(angle);
        const endY = y - nodeR * Math.sin(angle);
        return (
          <line
            key={`spoke-${i}`}
            x1={startX}
            y1={startY}
            x2={endX}
            y2={endY}
            stroke={colors.border}
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        );
      })}

      {/* Layer 2: center node */}
      <circle cx={cx} cy={cy} r={centerR} fill={colors.quaternary} />
      <text x={cx} y={cy - 6} textAnchor="middle" fill="white" fontSize="22" fontWeight="700" fontFamily={colors.sans}>
        {center}
      </text>
      {centerSub && (
        <text x={cx} y={cy + 22} textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize="14" fontFamily={colors.sans}>
          {centerSub}
        </text>
      )}

      {/* Layer 3: component nodes */}
      {positions.map(({ x, y }, i) => (
        <g key={`node-${i}`}>
          <circle cx={x} cy={y} r={nodeR} fill={colors.surface} stroke={colors.quinary} strokeWidth="3" />
          <text x={x} y={y - 6} textAnchor="middle" fill={colors.primary} fontSize="18" fontWeight="600" fontFamily={colors.sans}>
            {nodes[i].label}
          </text>
          {nodes[i].sublabel && (
            <text x={x} y={y + 18} textAnchor="middle" fill={colors.secondary} fontSize="13" fontFamily={colors.sans}>
              {nodes[i].sublabel}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
