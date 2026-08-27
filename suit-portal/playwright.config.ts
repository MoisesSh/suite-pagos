import { defineConfig, devices } from "@playwright/test";

// Nota: este portal todavía no tiene autenticación propia (es de cara al
// desarrollador externo, sin login) — a diferencia del panel de suit-frontend,
// no hace falta fixture de sesión/storageState.
export default defineConfig({
  testDir: "./e2e/specs",
  fullyParallel: true,
  retries: 1,
  webServer: {
    command: "npm run dev -- -p 3100",
    url: "http://localhost:3100",
    reuseExistingServer: true,
    timeout: 60_000,
  },
  use: {
    baseURL: "http://localhost:3100",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
