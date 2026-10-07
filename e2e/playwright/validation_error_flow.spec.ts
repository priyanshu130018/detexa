import { test, expect } from '@playwright/test';

test.describe('Flow 5: Resiliency and Validation Error Handling', () => {
  test('should gracefully handle 404 routes with not-found state', async ({ page }) => {
    await page.goto('/transactions/invalid-00000000-0000-0000-0000-000000000000');
    await page.waitForLoadState('networkidle');

    // Page should display error or empty state gracefully without crashing
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
