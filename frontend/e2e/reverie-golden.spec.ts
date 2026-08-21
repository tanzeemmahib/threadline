import { expect, test, type Page } from "@playwright/test";

function monitorPage(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const externalRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) externalRequests.push(request.url());
  });
  return { consoleErrors, pageErrors, externalRequests };
}

test("desktop judge presentation completes the six-scene evidence case", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const diagnostics = monitorPage(page);
  await page.goto("/demo?present=1");

  await expect(page.getByRole("heading", { name: /Same records\.\s*Different workflow\./ })).toBeVisible();
  await expect(page.getByLabel("Presentation controls")).toBeVisible();
  await expect(page.getByText("01 / 06", { exact: true }).first()).toBeVisible();

  const autoplay = page.getByRole("button", { name: "Autoplay" });
  await autoplay.click();
  await expect.poll(async () => page.getByLabel(/Presentation elapsed/).textContent()).not.toContain("00:00 / 01:32");
  await page.getByRole("button", { name: "Pause" }).click();
  const pausedAt = await page.getByLabel(/Presentation elapsed/).textContent();
  await page.waitForTimeout(550);
  await expect(page.getByLabel(/Presentation elapsed/)).toHaveText(pausedAt ?? "");

  await page.getByRole("button", { name: "Source-cited extraction" }).click();
  await expect(page.getByRole("heading", { name: "Source-cited extraction" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cross-script evidence stays attached to both sources." })).toBeVisible();
  await expect(page.locator('[lang="ar"][dir="rtl"]')).toContainText("يوسف الحسن");

  const sourceTrigger = page.getByRole("button", { name: /SPAN-/ }).first();
  await sourceTrigger.click();
  const dialog = page.getByRole("dialog", { name: /SPAN-/ });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Close source evidence" }).click();
  await expect.poll(async () => sourceTrigger.evaluate((element) => document.activeElement === element)).toBe(true);

  const backButton = page.getByRole("button", { name: "Back" });
  await backButton.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("heading", { name: "Source-cited extraction" })).toBeVisible();

  for (const scene of ["Supported thread", "Conflict gate", "Measured proof"]) {
    await page.getByRole("button", { name: scene }).click();
    await expect(page.getByRole("heading", { name: scene })).toBeVisible();
  }
  await expect(page.getByText("One connection recovered. One false merge prevented. Every decision traceable.")).toBeVisible();
  await page.getByRole("button", { name: "Restart" }).click();
  await expect(page.getByRole("heading", { name: "Human stakes" })).toBeVisible();

  expect(diagnostics.externalRequests).toEqual([]);
  expect(diagnostics.pageErrors).toEqual([]);
  expect(diagnostics.consoleErrors).toEqual([]);
});

test("Prompt Lab supports keyboard tabs, exact source evidence, and measured prompt diffs", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const diagnostics = monitorPage(page);
  await page.goto("/prompt-lab");

  await expect(page.getByRole("heading", { name: /One record pair\. Two reasoning paths\./ })).toBeVisible();
  const measuredLiveComparison = page.locator(".prompt-lab-live__available");
  if (await measuredLiveComparison.count()) {
    await expect(measuredLiveComparison).toContainText("LIVE MODEL PERFORMANCE");
    await expect(measuredLiveComparison).toContainText("Same input + config verified");
    const measuredRuns = measuredLiveComparison.getByRole("region", { name: "Measured live comparison case outcomes" });
    await expect(measuredRuns).toBeVisible();
    await expect(measuredRuns.locator("details")).toHaveCount(9);
    await measuredRuns.locator("summary").first().click();
    await expect(measuredRuns.locator("details").first().locator("tbody tr")).toHaveCount(8);
    const rawOutputLink = measuredRuns.locator("details").first().getByRole("link", { name: /Download sanitized raw \+ validated output/ }).first();
    await expect(rawOutputLink).toBeVisible();
    const rawResponse = await page.request.get(await rawOutputLink.getAttribute("href") ?? "");
    expect(rawResponse.ok()).toBe(true);
    expect(rawResponse.headers()["x-threadline-sha256"]).toMatch(/^[0-9a-f]{64}$/);
  } else {
    await expect(page.getByText("NOT MEASURED", { exact: true })).toBeVisible();
    await expect(page.getByText("ARTIFACT INVALID", { exact: true })).toHaveCount(0);
    await expect(page.getByText(/INCOMPLETE/)).toHaveCount(0);
  }
  await expect(page.locator('[lang="ar"][dir="rtl"]')).toContainText("يوسف الحسن");
  const firstTab = page.getByRole("tab").first();
  await firstTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab").nth(1)).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(page.getByRole("tab").nth(2)).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("BLOCKED — deterministic identity conflict", { exact: true })).toBeVisible();

  const v3Diff = page.getByText(/Inspect artifact-derived Prompt V2 → Prompt V3 diff/);
  await v3Diff.click();
  const diffRegion = page.getByRole("region", { name: "Line diff from Prompt V2 to Prompt V3" });
  await expect(diffRegion.locator("ins").first()).toBeVisible();
  await expect(diffRegion.locator("del").first()).toBeVisible();
  await expect(page.getByRole("note", { name: "Prompt V3 promotion tradeoff" })).toContainText("Promotion");

  expect(diagnostics.externalRequests).toEqual([]);
  expect(diagnostics.pageErrors).toEqual([]);
  expect(diagnostics.consoleErrors).toEqual([]);
});

test("reduced-motion presentation and 390px Prompt Lab stay complete without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const diagnostics = monitorPage(page);
  await page.goto("/demo?present=1");

  await expect(page.getByRole("button", { name: "Manual timing" })).toBeDisabled();
  await expect.poll(async () => page.locator(".reverie-judge__controls").evaluate((element) => getComputedStyle(element).position)).toBe("static");
  await page.getByRole("button", { name: "Next evidence" }).click();
  await expect(page.getByRole("heading", { name: "One-shot baseline" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await page.goto("/prompt-lab");
  await expect(page.getByRole("tablist", { name: "Prompt comparison cases" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  expect(diagnostics.externalRequests).toEqual([]);
  expect(diagnostics.pageErrors).toEqual([]);
  expect(diagnostics.consoleErrors).toEqual([]);
});
