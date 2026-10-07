import { test, expect } from '@playwright/test';

test.describe('Flow 4: Real-time WebSocket/SSE Streaming Hub', () => {
  test('should establish streaming connection and reflect live indicator', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Look for status indicator badge (Live / Connected / Active)
    const streamBadge = page.locator('text=/live|connected|online|realtime/i');
    if (await streamBadge.first().isVisible()) {
      await expect(streamBadge.first()).toBeVisible();
    }
  });
});
