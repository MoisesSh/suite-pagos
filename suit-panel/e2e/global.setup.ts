import { test as setup } from "@playwright/test";
import path from "path";

const authFile = path.join(__dirname, ".auth/storageState.json");

setup("autenticar y persistir sesion", async ({ page }) => {
  await page.goto("/login");
  await page.getByPlaceholder("usuario@ejemplo.com").fill(process.env.TEST_USER!);
  await page.getByPlaceholder("********").fill(process.env.TEST_PASS!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL("/discrepancias");
  await page.context().storageState({ path: authFile });
});
