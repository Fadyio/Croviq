import alexAvatar from "../assets/agents/alex.webp";
import irisAvatar from "../assets/agents/Iris.png";
import leoAvatar from "../assets/agents/leo.webp";

export type AgentId = "alex" | "leo" | "iris";

export const AGENT_IDENTITIES = {
  alex: {
    name: "Alex",
    role: "Data Scientist",
    focus: "Channel intelligence",
    avatar: alexAvatar,
  },
  leo: {
    name: "Leo",
    role: "Video Editor",
    focus: "Timeline editing",
    avatar: leoAvatar,
  },
  iris: {
    name: "Iris",
    role: "Quality Control",
    focus: "Release readiness",
    avatar: irisAvatar,
  },
} as const satisfies Record<AgentId, { name: string; role: string; focus: string; avatar: string }>;
