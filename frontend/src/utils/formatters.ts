/**
 * utils/formatters.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Standardized Indian currency (INR / ₹) and IST (Asia/Kolkata) formatters.
 */

/**
 * Formats a monetary amount in Indian Rupees (INR) using Indian numbering system (Lakhs, Crores).
 * Example: 125000 -> "₹1,25,000.00"
 */
export function formatINR(amount: number | null | undefined, showDecimals = true): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return '₹0.00';
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: showDecimals ? 2 : 0,
    maximumFractionDigits: showDecimals ? 2 : 0,
  }).format(amount);
}

/**
 * Formats a number in Indian numbering system (e.g., 1,25,000).
 */
export function formatIndianNumber(num: number | null | undefined): string {
  if (num === null || num === undefined || isNaN(num)) {
    return '0';
  }
  return new Intl.NumberFormat('en-IN').format(num);
}

/**
 * Formats a date string or timestamp in Indian Standard Time (Asia/Kolkata).
 */
export function formatIST(
  dateInput: string | number | Date | null | undefined,
  includeTime = true
): string {
  if (!dateInput) return '—';
  const date = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(date.getTime())) return String(dateInput);

  const options: Intl.DateTimeFormatOptions = {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(includeTime
      ? {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        }
      : {}),
  };

  return new Intl.DateTimeFormat('en-IN', options).format(date);
}

/**
 * Formats time only in IST (Asia/Kolkata).
 */
export function formatISTTime(dateInput: string | number | Date | null | undefined): string {
  if (!dateInput) return '—';
  const date = typeof dateInput === 'string' || typeof dateInput === 'number' ? new Date(dateInput) : dateInput;
  if (isNaN(date.getTime())) return String(dateInput);

  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }).format(date);
}
