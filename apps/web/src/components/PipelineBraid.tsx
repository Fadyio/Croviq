import React from "react";
import { motion, useReducedMotion } from "motion/react";

interface Stage {
  id: string;
  label: string;
  code: string;
  x: number;
  y: number;
}

const STAGES: Stage[] = [
  { id: "ingest", label: "Ingest", code: "RAW", x: 60, y: 100 },
  { id: "analyze", label: "Analysis", code: "AI", x: 180, y: 40 },
  { id: "cut", label: "Cut & EDL", code: "EDL", x: 300, y: 100 },
  { id: "qa", label: "Truth QA", code: "VERIFY", x: 420, y: 160 },
  { id: "ship", label: "Publish", code: "DIST", x: 540, y: 100 },
];

export const PipelineBraid: React.FC<{ className?: string }> = ({ className = "" }) => {
  const prefersReducedMotion = useReducedMotion();

  // Smooth multi-curve pipeline path spanning the stages
  const pathD =
    "M 60 100 C 120 100, 120 40, 180 40 C 240 40, 240 100, 300 100 C 360 100, 360 160, 420 160 C 480 160, 480 100, 540 100";

  return (
    <div className={`w-full max-w-[580px] select-none ${className}`} aria-hidden="true">
      <svg
        viewBox="0 0 600 200"
        className="w-full h-auto overflow-visible"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background Track Guide */}
        <path
          d={pathD}
          stroke="#23282D"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Secondary Braided Counter-Track */}
        <path
          d="M 60 100 C 120 100, 120 160, 180 160 C 240 160, 240 100, 300 100 C 360 100, 360 40, 420 40 C 480 40, 480 100, 540 100"
          stroke="#1C2024"
          strokeWidth="2"
          strokeDasharray="4 6"
          strokeLinecap="round"
        />

        {/* Active Animated Progression Pulse Track */}
        {!prefersReducedMotion ? (
          <motion.path
            d={pathD}
            stroke="#2355C5"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray="80 320"
            initial={{ strokeDashoffset: 400 }}
            animate={{ strokeDashoffset: 0 }}
            transition={{
              duration: 4.5,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        ) : (
          <path
            d={pathD}
            stroke="#2355C5"
            strokeWidth="3"
            strokeLinecap="round"
            strokeOpacity="0.6"
          />
        )}

        {/* Pipeline Stage Nodes */}
        {STAGES.map((stage, idx) => {
          return (
            <g key={stage.id} transform={`translate(${stage.x}, ${stage.y})`}>
              {/* Outer Node Ring */}
              <circle
                r="16"
                fill="#16191C"
                stroke="#2D3339"
                strokeWidth="1.5"
                className="transition-colors"
              />

              {/* Inner Indicator Core */}
              {!prefersReducedMotion ? (
                <motion.circle
                  r="6"
                  fill="#2355C5"
                  animate={{
                    scale: [1, 1.25, 1],
                    opacity: [0.7, 1, 0.7],
                  }}
                  transition={{
                    duration: 3,
                    repeat: Infinity,
                    delay: idx * 0.7,
                    ease: "easeInOut",
                  }}
                />
              ) : (
                <circle r="6" fill="#2355C5" />
              )}

              {/* Stage Typecode Chip */}
              <text
                y="-24"
                textAnchor="middle"
                fill="#78828C"
                fontSize="10"
                fontFamily="JetBrains Mono, monospace"
                fontWeight="500"
                letterSpacing="0.05em"
              >
                {stage.code}
              </text>

              {/* Stage Name */}
              <text
                y="32"
                textAnchor="middle"
                fill="#B0B7BE"
                fontSize="11"
                fontFamily="Inter, sans-serif"
                fontWeight="500"
              >
                {stage.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
