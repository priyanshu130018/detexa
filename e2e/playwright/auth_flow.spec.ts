import { test, expect } from '@playwright/test';

test.describe('Flow 1: Authentication & User Lifecycle', () => {
  const timestamp = Date.now();
  const testEmail = `analyst_${timestamp}@detexa.io`;
  const testPassword = 'Password@2026';

  test('should register a new compliance analyst, login, and access dashboard', async ({ page }) => {
    // 1. Navigate to Register
    await page.goto('/register');
    await page.waitForLoadState('networkidle');

    // 2. Fill registration form
    await page.fill('input[name="name"], input[placeholder*="name" i]', 'Security Officer');
    await page.fill('input[type="email"], input[name="email"]', testEmail);
    await page.fill('input[type="password"], input[name="password"]', testPassword);
    await page.click('button[type="submit"]');

    // 3. Confirm redirected to Login or Dashboard
    await page.waitForURL(/\/(login|dashboard|overview)/, { timeout: 10000 });

    // 4. Perform Login if on /login
    if (page.url().includes('/login')) {
      await page.fill('input[type="email"], input[name="email"]', testEmail);
      await page.fill('input[type="password"], input[name="password"]', testPassword);
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/(dashboard|overview)/, { timeout: 10000 });
    }

    // 5. Verify Authenticated Navigation Bar & Sidebar
    const navHeading = page.locator('nav, header, aside');
    await expect(navHeading).toBeVisible();
  });

  test('should reject invalid credentials with descriptive toast error', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="email"], input[name="email"]', 'unregistered_fraudster@detexa.io');
    await page.fill('input[type="password"], input[name="password"]', 'WrongPassword!123');
    await page.click('button[type="submit"]');

    // Expect alert/toast message
    const errorAlert = page.locator('text=/invalid|error|failed/i');
    await expect(errorAlert.first()).toBeVisible({ timeout: 5000 });
  });
});
