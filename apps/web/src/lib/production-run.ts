import type { components } from "../api/generated";

export type RunStageId =
  "uploaded" | "transcript" | "leo-edit" | "maya-review" | "edit-plan" | "render";
export type RunStageStatus = "completed" | "active" | "pending" | "failed";
export type ProcessingStage = "transcript" | "leo-edit" | "maya-review" | "edit-plan";

type EditorialRun = components["schemas"]["EditorialRun"];
type AgentActivity = components["schemas"]["AgentActivity"];

export interface PersistedProductionRun {
  uploadedAt?: string | null;
  transcriptCreatedAt?: string | null;
  editorialRun?: EditorialRun | null;
  activities?: AgentActivity[];
  uploaded: boolean;
  edlCreatedAt?: string | null;
}

export interface ProductionRunStage {
  id: RunStageId;
  label: string;
  status: RunStageStatus;
  durationMs?: number;
}

export interface RunStageOverrides {
  active?: ProcessingStage | null;
  failed?: ProcessingStage | null;
}

const elapsed = (start?: string | null, end?: string | null): number | undefined => {
  if (!start || !end) return undefined;
  const value = new Date(end).getTime() - new Date(start).getTime();
  return Number.isFinite(value) && value >= 0 ? value : undefined;
};

const lastActivityAt = (activities: AgentActivity[], agent: string): string | undefined =>
  activities
    .filter((activity) => activity.agent.toLowerCase() === agent)
    .map((activity) => activity.created_at)
    .filter((timestamp): timestamp is string => Boolean(timestamp))
    .sort()
    .at(-1);

const firstActivityAt = (activities: AgentActivity[], agent: string): string | undefined =>
  activities
    .filter((activity) => activity.agent.toLowerCase() === agent)
    .map((activity) => activity.created_at)
    .filter((timestamp): timestamp is string => Boolean(timestamp))
    .sort()
    .at(0);

export const deriveProductionRunStages = (
  run: PersistedProductionRun,
  overrides: RunStageOverrides = {},
): ProductionRunStage[] => {
  const editorialStatus = run.editorialRun?.status;
  const transcriptComplete = Boolean(run.transcriptCreatedAt);
  const leoComplete = editorialStatus === "reviewing" || editorialStatus === "completed";
  const mayaComplete = editorialStatus === "completed";
  const activities = run.activities ?? [];

  const stages: ProductionRunStage[] = [
    { id: "uploaded", label: "Uploaded", status: run.uploaded ? "completed" : "pending" },
    {
      id: "transcript",
      label: "Transcript",
      status: transcriptComplete ? "completed" : "pending",
      durationMs: elapsed(run.uploadedAt, run.transcriptCreatedAt),
    },
    {
      id: "leo-edit",
      label: "Leo Edit",
      status: leoComplete ? "completed" : editorialStatus === "analyzing" ? "active" : "pending",
      durationMs: elapsed(run.editorialRun?.started_at, lastActivityAt(activities, "leo")),
    },
    {
      id: "maya-review",
      label: "Maya Review",
      status: mayaComplete ? "completed" : editorialStatus === "reviewing" ? "active" : "pending",
      durationMs: elapsed(firstActivityAt(activities, "maya"), run.editorialRun?.completed_at),
    },
    {
      id: "edit-plan",
      label: "Edit Plan",
      status: run.edlCreatedAt ? "completed" : "pending",
      durationMs: elapsed(run.editorialRun?.completed_at, run.edlCreatedAt),
    },
    { id: "render", label: "Render", status: "pending" },
  ];

  if (overrides.active) {
    const stage = stages.find((candidate) => candidate.id === overrides.active);
    if (stage && stage.status !== "completed") stage.status = "active";
  }
  if (overrides.failed) {
    const stage = stages.find((candidate) => candidate.id === overrides.failed);
    if (stage) stage.status = "failed";
  }

  return stages;
};

export const nextMissingProcessingStage = (
  run: PersistedProductionRun,
): Exclude<ProcessingStage, "maya-review"> | null => {
  if (!run.uploaded) return null;
  if (!run.transcriptCreatedAt) return "transcript";
  if (run.editorialRun?.status !== "completed") return "leo-edit";
  if (!run.edlCreatedAt) return "edit-plan";
  return null;
};

export const formatStageDuration = (durationMs: number): string =>
  `${(durationMs / 1000).toFixed(1)}s`;
