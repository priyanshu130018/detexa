# Detexa Frontend Theme & 4-Color Standardization Report

**Date:** 2026-10-07  
**Status:** Completed & Verified  

---

## 1. Overview & Strict Color Palette Rules

The entire Detexa frontend has been refactored and standardized to use **strictly four colors** across light and dark modes:

| Color | Hex / Utility Tokens | Intended Context & Usage |
|---|---|---|
| **White** | `#ffffff`, `bg-white`, `text-white`, `border-white/*` | Primary backgrounds (light), primary text & high-contrast elements (dark), cards, modals |
| **Black** | `#000000`, `bg-black`, `text-black`, `border-black/*` | Primary backgrounds (dark), primary text & high-contrast elements (light), cards, modals |
| **Blue** | `#2563eb`, `#3b82f6`, `blue-600`, `blue-400`, `bg-blue-600/*` | Primary actions, branding, active navigation, step-up challenges, normal transactions, allow verdict, info badges |
| **Red** | `#dc2626`, `#ef4444`, `red-600`, `red-400`, `bg-red-600/*` | Fraud detection, high/critical risk badges, blocked decisions, security alerts, errors, destructive triggers |

> **Note:** Opacities of these four colors (e.g. `bg-black/5`, `bg-white/10`, `border-black/10`, `border-white/10`, `bg-blue-600/10`, `bg-red-600/10`) are used for backdrops, badges, hover states, and chart fills. No other colors (gray, slate, zinc, neutral, green, emerald, yellow, amber, orange, purple, violet, cyan, etc.) are used.

---

## 2. Theme Architecture & Persistence

### 2.1 Instant Theme Initialization (Anti-Flash)
- An inline script in `frontend/index.html` checks `localStorage.getItem('detexa_theme')` or system preferences before rendering, instantly applying or removing the `dark` class on `document.documentElement`.

### 2.2 Theme Context Provider
- [`ThemeContext.tsx`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/frontend/src/context/ThemeContext.tsx) serves as the single source of truth for the entire application.
- Theme toggles instantly update the `<html>` root class list, re-render React components, and persist to `localStorage` under key `'detexa_theme'`.

---

## 3. Standardized Components & Pages

### 3.1 Global & Layout Components
- **`tailwind.config.js`**: Cleaned of multi-color palettes; contains custom `brand` blues, `white`, `black`, `blue`, and `red`.
- **`index.html` & `index.css`**: Configured base styles for `body` (`bg-white text-black dark:bg-black dark:text-white`) and custom scrollbars using transparent black/white and blue accents.
- **`MainLayout.tsx`**: High-contrast wrapper with clean dark/light backgrounds.
- **`Navbar.tsx`**: Live stream connection dots (Blue for connected, Red for disconnected), instantaneous Sun/Moon theme toggle, Red signout trigger.
- **`Sidebar.tsx`**: Active nav highlighting with `bg-blue-600 text-white`, clean borders, and collapsible sidebar.

### 3.2 Common UI Components
- **`DecisionBadge.tsx`**:
  - `ALLOW` / `CHALLENGE`: Blue (`bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-600/30`)
  - `REVIEW` / `BLOCK`: Red (`bg-red-600/10 text-red-600 dark:text-red-400 border-red-600/30`)
- **`RiskBadge.tsx`**:
  - `Low` / `Medium`: Blue badges
  - `High` / `Critical`: Red badges
- **`ScoreGauge.tsx`**: Circular SVG gauge with high-risk red threshold (`#dc2626`) and low-risk blue threshold (`#2563eb`).
- **`SHAPChart.tsx`**: Directional SHAP feature importance chart with Red bars (`#dc2626`) pushing toward fraud, Blue bars (`#2563eb`) pushing toward legitimate.
- **`StatCard.tsx`**: Clean KPI cards with Blue and Red icon accents.
- **`Modal.tsx`**, **`EmptyState.tsx`**, **`LoadingSpinner.tsx`**: High contrast black/white backdrops and blue spinning indicators.

### 3.3 Application Pages
1. **`LandingPage.tsx`**: Hero section, architecture workflow diagrams, and feature cards using White, Black, Blue, and Red.
2. **`LoginPage.tsx` & `RegisterPage.tsx`**: High-contrast forms, blue primary buttons, red error messages.
3. **`OverviewPage.tsx`**: Real-time throughput stream chart (Blue & Red areas), live transaction feeds, decision distribution donut.
4. **`TransactionsPage.tsx`**: Transaction table, pagination, search, status filters, and live stream updates.
5. **`TransactionDetailPage.tsx`**: 360° inspector with SHAP waterfall, Redis sliding hot feature store, Neo4j graph signals, and decision override modal.
6. **`AlertsPage.tsx`**: Security incident timeline (Red/Blue area stacks), incident status filters, triage modal with SHAP explainability.
7. **`InvestigationPage.tsx`**: Interactive sandbox with preset scenarios, parameter inputs, real-time inference execution, and decision arbitration rules.
8. **`GraphInvestigationPage.tsx`**: Neo4j SVG subgraph visualizer with node types (User, Device, IP in Blue shades; Transaction in Red; Merchant in Black/White), entity inspector, and detected fraud ring table.
9. **`ModelStatisticsPage.tsx`**: ML booster registry card, AUC-ROC/Precision/Recall/F1 metrics, dynamic policy bands (ALLOW/CHALLENGE in Blue, REVIEW/BLOCK in Red), and canonical 61-feature dictionary.
10. **`PredictPage.tsx`**: Single credit inference, batch CSV upload scoring, and Isolation Forest behavioral anomaly detector.
11. **`BehaviorPage.tsx`**: Country session breakdown bar chart (Blue for Total, Red for VPN/TOR) and risk distribution pie chart.

---

## 4. Verification & Validation

1. **Static Analysis & Keyword Scan:**
   - Scanned all `.tsx`, `.ts`, `.css`, and `.html` files for disallowed color classes (`slate`, `gray`, `zinc`, `neutral`, `emerald`, `green`, `yellow`, `amber`, `orange`, `purple`, `violet`, `pink`, `cyan`, `teal`, `indigo`, `rose`).
   - Verified 0 remaining disallowed CSS utility classes or non-compliant color variables.
2. **Build & Typecheck:**
   - Ran `docker compose exec frontend npm run build` (`tsc && vite build`).
   - Build compiled **2,390 modules** with **0 TypeScript errors** and produced production bundles (`dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`).
3. **Runtime Theme Switching:**
   - Theme toggle immediately flips between light (`bg-white text-black`) and dark (`bg-black text-white`) across all routes and components with persistent state in `localStorage`.
