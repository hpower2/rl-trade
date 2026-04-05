import { defineConfig, devices } from "@playwright/test";

const previewPort = Number(process.env.PLAYWRIGHT_PORT ?? "4173");
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${previewPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  outputDir: "./output/playwright/test-results",
  reporter: "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
  webServer: {
    command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${previewPort} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
