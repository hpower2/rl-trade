import { test, expect } from "./fixtures/operator-workspace";

test("covers the browser happy path from login through paper-trading controls", async ({
  page,
  operatorWorkspace,
}) => {
  await operatorWorkspace.login();

  await page.getByRole("button", { name: /validate symbol/i }).click();
  await expect(page.getByText(/validation passed/i)).toBeVisible();
  await expect(page.getByRole("table", { name: /symbol status snapshot/i })).toContainText("EURUSD");

  await page.getByRole("button", { name: /request training/i }).click();
  await expect(page.getByText(/training request queued/i)).toBeVisible();
  await expect(page.getByText(/ingestion queue · EURUSD/i)).toBeVisible();

  await operatorWorkspace.emitPipelineProgress({
    eventType: "ingestion_progress",
    jobId: 901,
    progressPercent: 35,
    status: "running",
    symbolCode: "EURUSD",
  });
  await operatorWorkspace.emitPipelineProgress({
    eventType: "preprocessing_progress",
    jobId: 902,
    progressPercent: 65,
    status: "running",
    symbolCode: "EURUSD",
  });
  await operatorWorkspace.emitPipelineProgress({
    eventType: "training_progress",
    jobId: 903,
    progressPercent: 90,
    status: "running",
    symbolCode: "EURUSD",
  });

  await expect(page.getByText(/preprocessing queue · EURUSD/i)).toBeVisible();
  await expect(page.getByText(/training queue · EURUSD/i)).toBeVisible();
  await expect(page.getByText(/training_progress · live/i)).toBeVisible();

  await page.getByRole("link", { name: /pipeline/i }).click();
  await expect(
    page.getByRole("heading", { name: /ingestion, preprocessing, and training watch desk/i }),
  ).toBeVisible();
  await expect(page.getByText(/operator intake and current downstream status/i)).toBeVisible();
  await expect(page.getByText(/stage-specific queue health/i)).toBeVisible();
  await expect(page.getByText(/training queue · EURUSD/i)).toBeVisible();
  await expect(page.getByText(/90% complete/i)).toBeVisible();

  await operatorWorkspace.emitApproval("EURUSD");
  await page.getByRole("link", { name: /models/i }).click();
  await expect(page.getByRole("heading", { name: /approval and evaluation desk/i })).toBeVisible();
  await expect(page.getByRole("table", { name: /approved symbols/i })).toContainText("EURUSD");
  await expect(page.getByText(/78.6%/i).first()).toBeVisible();

  await page.getByRole("link", { name: /paper trading/i }).click();
  await expect(page.getByRole("heading", { name: /demo runtime control plane/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /start runtime/i })).toBeEnabled();

  await page.getByRole("button", { name: /start runtime/i }).click();
  await expect(page.getByText(/runtime enabled/i)).toBeVisible();
  await expect(page.getByText(/1 accepted signals/i)).toBeVisible();
  await expect(page.getByText(/EURUSD · long/i).first()).toBeVisible();

  await page.getByRole("button", { name: /stop runtime/i }).click();
  await expect(page.getByText(/ready to start/i)).toBeVisible();
});
