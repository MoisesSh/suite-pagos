import { defineConfig, devices } from "@playwright/test";
import { config } from "dotenv";

config({ path: ".env" });

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 1,
  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: /global\.setup\.ts/,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], storageState: "e2e/.auth/storageState.json" },
      dependencies: ["setup"],
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"], storageState: "e2e/.auth/storageState.json" },
      dependencies: ["setup"],
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"], storageState: "e2e/.auth/storageState.json" },
      dependencies: ["setup"],
    },
  ],
});
