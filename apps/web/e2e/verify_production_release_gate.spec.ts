import { expect, test } from "@playwright/test";
import * as fs from "node:fs";

test.describe("FINAL PRODUCTION RELEASE GATE - LIVE DEPLOYED APP", () => {
  test.setTimeout(480000);

  test("End-to-End Live Production Verification on app.croviq.app", async ({ page, request }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const failedRequests: { url: string; status: number; method: string }[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });

    page.on("response", (res) => {
      if (res.status() >= 400 && !res.url().includes("/api/auth/me")) {
        failedRequests.push({
          url: res.url(),
          status: res.status(),
          method: res.request().method(),
        });
      }
    });

    const authPayload = JSON.parse(fs.readFileSync("/tmp/browser-auth-payload.json", "utf-8"));
    let idToken = authPayload.user.stsTokenManager.accessToken;
    const productionId = "prod_6d3399e433a4";

    // Refresh token via REST
    const tokenRes = await request.post(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=${authPayload.apiKey}`, {
      data: { token: fs.readFileSync("/tmp/custom-token.txt", "utf-8").trim(), returnSecureToken: true },
    });
    if (tokenRes.ok()) {
      const tokenData = await tokenRes.json();
      idToken = tokenData.idToken;
      authPayload.user.stsTokenManager.accessToken = tokenData.idToken;
      authPayload.user.stsTokenManager.refreshToken = tokenData.refreshToken;
    }
    // 1. Authenticate via IndexedDB
    await page.goto("https://app.croviq.app/login");
    await page.evaluate(async (data) => {
      const { promise, resolve, reject } = Promise.withResolvers<void>();
      const req = indexedDB.open("firebaseLocalStorageDb", 1);
      req.onupgradeneeded = (e) => {
        const target = e.target as IDBOpenDBRequest | null;
        const db = target?.result;
        if (db && !db.objectStoreNames.contains("firebaseLocalStorage")) {
          db.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
        }
      };
      req.onsuccess = (e) => {
        const target = e.target as IDBOpenDBRequest | null;
        const db = target?.result;
        if (!db) {
          reject(new Error("IndexedDB unavailable"));
          return;
        }
        const tx = db.transaction("firebaseLocalStorage", "readwrite");
        const store = tx.objectStore("firebaseLocalStorage");
        store.put({ fbase_key: `firebase:authUser:${data.apiKey}:[DEFAULT]`, value: data.user });
        tx.oncomplete = () => resolve();
        tx.onerror = (err) => reject(err);
      };
      req.onerror = (err) => reject(err);
      await promise;
    }, authPayload);

    // Wait for authenticated home page to load first
    await page.goto("https://app.croviq.app/app");
    await expect(page.getByText(/Croviq|Sample|New Project/i).first()).toBeVisible({ timeout: 20000 });

    // 2. Open Production Editor
    await page.goto(`https://app.croviq.app/productions/${productionId}/editor`);
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    const bodyText = await page.evaluate(() => document.body.innerText);
    console.log("PAGE_CURRENT_URL:", currentUrl);
    console.log("PAGE_BODY_SNIPPET:", bodyText.slice(0, 300));
    await expect(page.locator("body")).toBeVisible();

    // 3. Test Edited Preview Playback
    const editedToggle = page.getByTestId("preview-toggle-edited");
    await expect(editedToggle).toBeVisible({ timeout: 15000 });
    await editedToggle.click();
    await page.waitForTimeout(1000);

    const video = page.locator("video").first();
    await expect(video).toBeVisible();
    const playResult = await page.evaluate(async () => {
      const v = document.querySelector("video");
      if (!v) return { ok: false, error: "no video" };
      v.muted = true;
      try {
        await v.play();
        const playing = !v.paused && v.currentTime >= 0;
        v.pause();
        return { ok: playing, currentTime: v.currentTime, duration: v.duration };
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return { ok: false, error: message };
      }
    });
    expect(playResult.ok).toBe(true);

    // 4. Select Charon & Generate Voiceover
    const setCharonRes = await request.put("https://app.croviq.app/api/workspace/agent-settings/voice", {
      headers: { Authorization: `Bearer ${idToken}` },
      data: { narration_mode: "studio_voice", selected_voice: "Charon", language: "en-US" },
    });
    expect(setCharonRes.status()).toBe(200);

    // Trigger Studio Voice generation with Charon
    const studioVoiceRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/studio-voice`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    expect(studioVoiceRes.status()).toBe(200);
    const studioVoiceData = await studioVoiceRes.json();
    expect(studioVoiceData.result.status).toBe("completed");
    expect(studioVoiceData.result.voice_id).toBe("Charon");
    const charonArtifactId = studioVoiceData.result.preview_artifact_id;
    // 5. Verify Voiceover Preview in UI
    await page.reload();
    await expect(page.getByText("Test.mp4").first()).toBeVisible({ timeout: 20000 });
    const voiceoverToggle = page.getByTestId("preview-toggle-studio-voice").or(page.getByTestId("preview-toggle-voiceover"));
    await expect(voiceoverToggle).toBeVisible({ timeout: 20000 });
    await voiceoverToggle.click();

    // Verify timeline contains Voiceover blocks
    const timelineVoBlocks = page.locator("[data-track-id='voiceover'], [data-block-type='voiceover'], .timeline-block-voiceover, div:has-text('Studio Voiceover')");
    expect(await timelineVoBlocks.count()).toBeGreaterThan(0);

    // Play Voiceover at beginning, middle, and end
    const voPlayPositions = await page.evaluate(async () => {
      const v = document.querySelector("video");
      if (!v) return { ok: false };
      v.muted = true;
      const duration = v.duration || 58;
      const delay = (ms: number) => {
        const { promise, resolve } = Promise.withResolvers<void>();
        setTimeout(resolve, ms);
        return promise;
      };

      // Beginning
      v.currentTime = 1;
      await v.play();
      await delay(500);
      const pos1 = v.currentTime;

      // Middle
      v.currentTime = duration / 2;
      await v.play();
      await delay(500);
      const pos2 = v.currentTime;

      // End
      v.currentTime = duration - 3;
      await v.play();
      await delay(500);
      const pos3 = v.currentTime;

      v.pause();
      return { ok: true, pos1, pos2, pos3, duration };
    });
    expect(voPlayPositions.ok).toBe(true);
    // 6. Build Initial Final Mix with Charon
    const charonFinalMixRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/renders/final-mix`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    expect(charonFinalMixRes.status()).toBe(200);
    const charonFinalMixData = await charonFinalMixRes.json();
    expect(charonFinalMixData.status).toBe("completed");

    // 7. Hard Refresh and verify Voiceover persists
    await page.reload();
    await expect(page.getByText("Test.mp4").first()).toBeVisible({ timeout: 20000 });
    await expect(voiceoverToggle).toBeVisible({ timeout: 15000 });

    // 8. Select Kore & Generate New Voiceover Artifact
    const switchVoiceRes = await request.put("https://app.croviq.app/api/workspace/agent-settings/voice", {
      headers: { Authorization: `Bearer ${idToken}` },
      data: { narration_mode: "studio_voice", selected_voice: "Kore", language: "en-US" },
    });
    expect(switchVoiceRes.status()).toBe(200);

    const koreVoiceRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/studio-voice`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    expect(koreVoiceRes.status()).toBe(200);
    const koreVoiceData = await koreVoiceRes.json();
    expect(koreVoiceData.result.status).toBe("completed");
    expect(koreVoiceData.result.voice_id).toBe("Kore");
    const koreArtifactId = koreVoiceData.result.preview_artifact_id;
    expect(koreArtifactId).toBeTruthy();
    // 8. Second Hard Refresh
    await page.reload();
    await expect(page.getByText("Test.mp4").first()).toBeVisible({ timeout: 20000 });
    await expect(voiceoverToggle).toBeVisible({ timeout: 15000 });

    // 9. Final Mix Verification
    // Check playback status -> final_mix must be needs_regeneration / unavailable
    const stalePlaybackRes = await request.get(`https://app.croviq.app/api/productions/${productionId}/playback`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    const stalePlayback = await stalePlaybackRes.json();
    expect(stalePlayback.final_mix.status).toBe("needs_regeneration");
    expect(stalePlayback.final_mix.available).toBe(false);

    // Rebuild Final Mix
    const rebuildFinalMixRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/renders/final-mix`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    expect(rebuildFinalMixRes.status()).toBe(200);
    const finalMixData = await rebuildFinalMixRes.json();
    expect(finalMixData.status).toBe("completed");
    const finalMixArtifactId = finalMixData.artifact_id;

    // Verify ready Final Mix playback
    const readyPlaybackRes = await request.get(`https://app.croviq.app/api/productions/${productionId}/playback`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    const readyPlayback = await readyPlaybackRes.json();
    expect(readyPlayback.final_mix.status).toBe("ready");
    expect(readyPlayback.final_mix.available).toBe(true);
    expect(readyPlayback.final_mix.artifact_id).toBe(finalMixArtifactId);
    expect(readyPlayback.final_mix.voice_id).toBe("Kore");

    // 10. Iris / Release Gates
    await page.goto(`https://app.croviq.app/productions/${productionId}/release`);
    await expect(page.locator("h1, h2, header")).toContainText(/Release|Quality|Test\.mp4/i, { timeout: 20000 });

    // Test sending 4 modes to Iris
    const modes = ["original", "edited", "voiceover", "final_mix"];
    for (const mode of modes) {
      const irisRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/release-review`, {
        headers: { Authorization: `Bearer ${idToken}` },
        data: { preview_mode: mode },
      });
      expect(irisRes.status()).toBe(200);
      const irisData = await irisRes.json();
      expect(irisData.verdict).toBeTruthy();
      expect(irisData.preview_mode).toBe(mode);
      if (mode === "original") {
        // Original has uncut bad sections -> strict findings
        expect(irisData.findings.length).toBeGreaterThan(0);
      }
    }

    // Test Title & Description AI generation with Reese
    const reeseRes = await request.post(`https://app.croviq.app/api/productions/${productionId}/packaging/regenerate-reese`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    expect(reeseRes.status()).toBe(200);
    const reeseData = await reeseRes.json();
    expect(reeseData.proposal).toBeTruthy();
    expect(reeseData.proposal.primary_title).toBeTruthy();
    expect(reeseData.proposal.description).toBeTruthy();

    // Save metadata overrides
    const saveRes = await request.patch(`https://app.croviq.app/api/productions/${productionId}/packaging`, {
      headers: { Authorization: `Bearer ${idToken}` },
      data: {
        selected_title: reeseData.proposal.primary_title,
        custom_description: reeseData.proposal.description,
      },
    });
    expect(saveRes.status()).toBe(200);
    const saveData = await saveRes.json();
    expect(saveData.effective_title).toBe(reeseData.proposal.primary_title);
    expect(saveData.effective_description).toBe(reeseData.proposal.description);

    // Output complete diagnostic summary
    fs.writeFileSync(
      "/tmp/production-gate-results.json",
      JSON.stringify(
        {
          success: true,
          productionId,
          charonArtifactId,
          koreArtifactId,
          finalMixArtifactId,
          consoleErrors,
          pageErrors,
          failedRequests,
        },
        null,
        2
      )
    );
  });
});
