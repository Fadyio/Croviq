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

  test("requires post-render review when preview is rendered but review is not yet recorded", () => {
    const previewRenderedRun: PersistedProductionRun = {
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
      renderReview: null,
    };

    expect(nextMissingProcessingStage(previewRenderedRun)).toBe("render");
  });

  test("marks render completed and ends autonomous loop when preview is approved and master render is complete", () => {
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
      renderReview: {
        review_id: "rrv_01",
        production_id: "prod_01",
        edl_id: "edl_01",
        preview_artifact_id: "art_prev_01",
        agent: "maya",
        model: "gemini-3.7-flash",
        verdict: "APPROVE",
        summary: "The dialogue flows naturally. Edit approved.",
        issues: [],
        approved_for_master: true,
        confidence: 0.95,
        created_at: "2026-08-27T10:00:20Z",
      },
      masterStatus: "completed",
      masterCompletedAt: "2026-08-27T10:00:25Z",
    };

    const stages = deriveProductionRunStages(renderCompleteRun);
    const renderStage = stages.find((s) => s.id === "render");
    expect(renderStage).toMatchObject({ id: "render", status: "completed" });
    expect(nextMissingProcessingStage(renderCompleteRun)).toBeNull();
  });

  test("marks render completed with short artifact present", () => {
    const shortCompleteRun: PersistedProductionRun = {
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
      renderReview: {
        review_id: "rrv_01",
        production_id: "prod_01",
        edl_id: "edl_01",
        preview_artifact_id: "art_prev_01",
        agent: "maya",
        model: "gemini-3.7-flash",
        verdict: "APPROVE",
        summary: "The dialogue flows naturally. Edit approved.",
        issues: [],
        approved_for_master: true,
        confidence: 0.95,
        created_at: "2026-08-27T10:00:20Z",
      },
      masterStatus: "completed",
      masterCompletedAt: "2026-08-27T10:00:25Z",
      shortStatus: "completed",
      shortCompletedAt: "2026-08-27T10:00:28Z",
    };

    const stages = deriveProductionRunStages(shortCompleteRun);
    const renderStage = stages.find((s) => s.id === "render");
    expect(renderStage).toMatchObject({ id: "render", status: "completed" });
    expect(nextMissingProcessingStage(shortCompleteRun)).toBeNull();
  });

  test("marks render failed when correction pass fails and needs manual review", () => {
    const needsReviewRun: PersistedProductionRun = {
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
      needsManualReview: true,
    };

    const stages = deriveProductionRunStages(needsReviewRun);
    const renderStage = stages.find((s) => s.id === "render");
    expect(renderStage).toMatchObject({
      id: "render",
      status: "failed",
      subStatus: "Needs manual review",
    });
    expect(nextMissingProcessingStage(needsReviewRun)).toBeNull();
  });
});
