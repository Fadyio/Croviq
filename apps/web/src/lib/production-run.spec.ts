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
});
