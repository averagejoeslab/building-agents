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

  const angles = [-Math.PI / 2, Math.PI / 2 + Math.PI / 3, Math.PI / 2 - Math.PI / 3];
  const vertices = angles.map((a) => ({
    x: cx + r * Math.cos(a),
    y: cy + r * Math.sin(a),
  }));

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxHeight: "70vh" }}>
      <polygon
        points={vertices.map((v) => `${v.x},${v.y}`).join(" ")}
        fill="none"
        stroke={colors.border}
        strokeWidth="2"
        strokeDasharray="6 4"
      />
      <circle cx={cx} cy={cy} r="80" fill={colors.quaternary} />
      <text x={cx} y={cy - 6} textAnchor="middle" fill="white" fontSize="22" fontWeight="700" fontFamily={colors.sans}>
        {center}
      </text>
      {centerSub && (
        <text x={cx} y={cy + 22} textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize="14" fontFamily={colors.sans}>
          {centerSub}
        </text>
      )}
      {vertices.map((v, i) => (
        <g key={i}>
          <circle cx={v.x} cy={v.y} r={nodeR} fill={colors.surface} stroke={colors.quinary} strokeWidth="3" />
          <text x={v.x} y={v.y - 6} textAnchor="middle" fill={colors.primary} fontSize="18" fontWeight="600" fontFamily={colors.sans}>
            {nodes[i].label}
          </text>
          {nodes[i].sublabel && (
            <text x={v.x} y={v.y + 18} textAnchor="middle" fill={colors.secondary} fontSize="13" fontFamily={colors.sans}>
              {nodes[i].sublabel}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}
