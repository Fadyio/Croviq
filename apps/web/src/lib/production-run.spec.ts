import { expect, test } from "@playwright/test";
import {
  deriveProductionRunStages,
  nextMissingProcessingStage,
  type PersistedProductionRun,
} from "./production-run";

const pendingUpload: PersistedProductionRun = {
  uploaded: false,
  uploadedAt: null,
  transcriptCreatedAt: null,
  editorialRun: null,
  edlCreatedAt: null,
};

test.describe("production run state", () => {
  test("keeps Uploaded pending and does not start downstream work before upload completes", () => {
    const stages = deriveProductionRunStages(pendingUpload);

    expect(stages[0]).toMatchObject({ id: "uploaded", status: "pending" });
    expect(nextMissingProcessingStage(pendingUpload)).toBeNull();
  });

  test("starts transcription after canonical media status becomes uploaded", () => {
    const uploadedRun = { ...pendingUpload, uploaded: true };

    expect(deriveProductionRunStages(uploadedRun)[0]).toMatchObject({
      id: "uploaded",
      status: "completed",
    });
    expect(nextMissingProcessingStage(uploadedRun)).toBe("transcript");
  });

  test("starts render after canonical EDL plan is assembled", () => {
    const edlCompleteRun: PersistedProductionRun = {
      uploaded: true,
      uploadedAt: "2026-08-27T10:00:00Z",
      transcriptCreatedAt: "2026-08-27T10:00:05Z",
      editorialRun: {
        run_id: "run_01",
        production_id: "prod_01",
        editor_proposal_id: "prop_01",
        director_review_id: "rev_01",
        status: "completed",
        started_at: "2026-08-27T10:00:05Z",
        completed_at: "2026-08-27T10:00:10Z",
      },
      edlCreatedAt: "2026-08-27T10:00:12Z",
    };

    const stages = deriveProductionRunStages(edlCompleteRun);
    const renderStage = stages.find((s) => s.id === "render");
    expect(renderStage).toMatchObject({ id: "render", status: "pending" });
    expect(nextMissingProcessingStage(edlCompleteRun)).toBe("render");
  });

  test("marks render completed and ends autonomous loop when preview is rendered", () => {
    const renderCompleteRun: PersistedProductionRun = {
      uploaded: true,
      uploadedAt: "2026-08-27T10:00:00Z",
      transcriptCreatedAt: "2026-08-27T10:00:05Z",
      editorialRun: {
        run_id: "run_01",
        production_id: "prod_01",
        editor_proposal_id: "prop_01",
        director_review_id: "rev_01",
        status: "completed",
        started_at: "2026-08-27T10:00:05Z",
        completed_at: "2026-08-27T10:00:10Z",
      },
      edlCreatedAt: "2026-08-27T10:00:12Z",
      renderCompletedAt: "2026-08-27T10:00:16Z",
      renderStatus: "completed",
      renderDurationMs: 4000,
    };

    const stages = deriveProductionRunStages(renderCompleteRun);
    const renderStage = stages.find((s) => s.id === "render");
    expect(renderStage).toMatchObject({ id: "render", status: "completed", durationMs: 4000 });
    expect(nextMissingProcessingStage(renderCompleteRun)).toBeNull();
  });
});
