import { expect, test } from "@playwright/test";

for (const viewport of [
  { width: 390, height: 844 },
  { width: 1280, height: 800 },
]) {
  test(`chat launcher clears footer links at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.goto("http://127.0.0.1:3005");
    const launcher = page.getByRole("button", {
      name: "Chat with TrackFlow",
      exact: true,
    });
    const footer = page.getByRole("contentinfo");
    await footer.scrollIntoViewIfNeeded();
    await expect(async () => {
      const launcherBox = await launcher.boundingBox();
      const footerBox = await footer.boundingBox();
      expect(launcherBox).not.toBeNull();
      expect(footerBox).not.toBeNull();
      expect(launcherBox!.y + launcherBox!.height).toBeLessThanOrEqual(
        footerBox!.y - 8,
      );
    }).toPass({ timeout: 3000 });
    for (const name of ["Careers", "Privacy Policy", "TrackFlow on LinkedIn"]) {
      const link = footer.getByRole("link", { name, exact: true });
      await expect(link).toBeVisible();
      expect(
        await link.evaluate((element) => {
          const box = element.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.left + box.width / 2,
            box.top + box.height / 2,
          );
          return hit === element || element.contains(hit);
        }),
      ).toBe(true);
    }
    await page.screenshot({
      path: `/private/tmp/trackflow-footer-${viewport.width}.png`,
    });
    await launcher.click();
    const panel = page.getByRole("dialog", { name: "TrackFlow Support" });
    await panel.getByRole("textbox", { name: "Your question" }).fill("Hello");
    await panel.getByRole("button", { name: "Send", exact: true }).click();
    await expect(panel.getByRole("log")).toContainText(
      "Hello! Welcome to TrackFlow.",
    );
    await expect(panel.getByRole("alert")).toHaveCount(0);
    await page.screenshot({
      path: `/private/tmp/trackflow-greeting-${viewport.width}.png`,
    });
    await panel
      .getByRole("combobox", { name: "Policy country" })
      .selectOption("US");
    await panel
      .getByRole("textbox", { name: "Your question" })
      .fill("What is your delivery policy?");
    await panel.getByRole("button", { name: "Send", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText(
      "Policy answers have not been enabled in this demo yet.",
    );
    await page.screenshot({
      path: `/private/tmp/trackflow-policy-disabled-${viewport.width}.png`,
    });
    await panel.getByRole("button", { name: "Close support chat" }).click();
    await expect(launcher).toBeFocused();
    await page.goto("http://127.0.0.1:3005/careers");
    await footer.scrollIntoViewIfNeeded();
    await expect(async () => {
      const launcherBox = await launcher.boundingBox();
      const footerBox = await footer.boundingBox();
      expect(launcherBox!.y + launcherBox!.height).toBeLessThanOrEqual(
        footerBox!.y - 8,
      );
    }).toPass({ timeout: 3000 });
  });
}
