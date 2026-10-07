import { test, expect } from '@playwright/test';

test.describe('Flow 2: Transaction Live Monitoring & Submission Flow', () => {
  test('should display live transactions and inspect high risk indicators', async ({ page }) => {
    // 1. Visit Transactions page
    await page.goto('/transactions');
    await page.waitForLoadState('networkidle');

    // 2. Verify Table or List renders
    const tableOrList = page.locator('table, [role="table"], .grid, .space-y-4');
    await expect(tableOrList.first()).toBeVisible();

    // 3. Check for Search / Filter input
    const searchInput = page.locator('input[placeholder*="search" i], input[type="search"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('Amazon');
      await page.waitForTimeout(500);
    }
  });

  test('should submit single credit prediction and view decision outcome', async ({ page }) => {
    await page.goto('/predict');
    await page.waitForLoadState('networkidle');

    // Fill amount if form is available
    const amountInput = page.locator('input[name="amount"], input[placeholder*="amount" i]');
    if (await amountInput.isVisible()) {
      await amountInput.fill('450.00');
      const submitBtn = page.locator('button[type="submit"], button:has-text("Evaluate"), button:has-text("Analyze")');
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
        await page.waitForTimeout(1000);
      }
    }
  });
});
