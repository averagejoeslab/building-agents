import { colors } from "../theme";

export function StateSplit() {
  return (
    <svg viewBox="0 0 1000 360" width="100%" style={{ maxHeight: "50vh" }}>
      <defs>
        <marker id="ss-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 Z" fill={colors.quaternary} />
        </marker>
      </defs>

      {/* API server box — ghosted, no state */}
      <g>
        <rect x={620} y={70} width={300} height={220} rx="12" fill={colors.surface} stroke={colors.secondary} strokeDasharray="6 4" strokeWidth="2" />
        <text x={770} y={104} textAnchor="middle" fontSize="20" fontWeight="700" fill={colors.secondary} fontFamily={colors.sans}>
          Messages API
        </text>
        <text x={770} y={130} textAnchor="middle" fontSize="14" fill={colors.secondary} fontFamily={colors.sans}>
          (stateless)
        </text>
        <text x={770} y={184} textAnchor="middle" fontSize="48" opacity={0.4}>
          👻
        </text>
        <text x={770} y={234} textAnchor="middle" fontSize="14" fill={colors.secondary} fontFamily={colors.sans}>
          No memory between calls.
        </text>
        <text x={770} y={254} textAnchor="middle" fontSize="14" fill={colors.secondary} fontFamily={colors.sans}>
          Each request stands alone.
        </text>
      </g>

      {/* Program box — colored, holds state */}
      <g>
        <rect x={80} y={50} width={420} height={260} rx="12" fill={colors.surface} stroke={colors.quinary} strokeWidth="3" />
        <text x={290} y={84} textAnchor="middle" fontSize="20" fontWeight="700" fill={colors.quinary} fontFamily={colors.sans}>
          Your program
        </text>
        <text x={290} y={108} textAnchor="middle" fontSize="14" fill={colors.secondary} fontFamily={colors.sans}>
          holds the conversation
        </text>

        {/* messages list */}
        <g transform="translate(110, 130)">
          {[
            { role: "user", text: "Hi!", color: colors.quaternary },
            { role: "assistant", text: "Hello.", color: colors.quinary },
            { role: "user", text: "What is 2+2?", color: colors.quaternary },
            { role: "assistant", text: "4.", color: colors.quinary },
          ].map((m, i) => (
            <g key={i}>
              <rect x={0} y={i * 36} width={360} height={30} rx="4" fill={colors.tertiary} stroke={m.color} strokeWidth="1.5" />
              <text x={10} y={i * 36 + 20} fontSize="13" fontFamily={colors.mono} fill={m.color} fontWeight="600">
                {m.role}:
              </text>
              <text x={84} y={i * 36 + 20} fontSize="13" fontFamily={colors.mono} fill={colors.primary}>
                {m.text}
              </text>
            </g>
          ))}
        </g>
      </g>

      {/* Arrow between */}
      <g>
        <line x1={500} y1={180} x2={620} y2={180} stroke={colors.quaternary} strokeWidth="3" markerEnd="url(#ss-arr)" />
        <text x={560} y={170} textAnchor="middle" fontSize="14" fill={colors.quaternary} fontWeight="600" fontFamily={colors.sans}>
          full messages
        </text>
        <text x={560} y={200} textAnchor="middle" fontSize="13" fill={colors.secondary} fontFamily={colors.sans}>
          every call
        </text>
      </g>
    </svg>
  );
}
