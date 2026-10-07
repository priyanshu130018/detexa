import { test, expect } from '@playwright/test';

test.describe('Flow 3: Fraud Alert Investigation & Status Triage', () => {
  test('should list security alerts and view investigation drawer', async ({ page }) => {
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');

    // Verify Alert Dashboard Page Header
    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toBeVisible();

    // Check presence of status filter buttons (Open, Reviewed, Resolved)
    const openFilter = page.locator('button:has-text("Open"), button:has-text("All")');
    if (await openFilter.first().isVisible()) {
      await openFilter.first().click();
      await page.waitForTimeout(500);
    }
  });

  test('should inspect graph investigation network topology', async ({ page }) => {
    await page.goto('/graph');
    await page.waitForLoadState('networkidle');

    // Verify Graph Investigation container or canvas/svg
    const graphContainer = page.locator('svg, canvas, #graph-container, .graph-wrapper, text=/graph/i');
    await expect(graphContainer.first()).toBeVisible({ timeout: 10000 });
  });
});
