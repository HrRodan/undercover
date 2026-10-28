/# Brand

## Aesthetic Direction

**Nordic Obsidian & Precision Daylight** — an executive fintech aesthetic inspired by high-craft operational tools. Crisp typographic hierarchy, tactile surface elevation with hairline borders, and high-contrast semantic accents built for long claims-handling sessions in both light and dark environments.

## Fonts

From Google Fonts:

- **Headings**: Space Grotesk (weights 600, 700; tight tracking `-0.02em`)
- **Body and UI controls**: Plus Jakarta Sans (weights 400, 500, 600)
- **Accent (editorial callouts, quotes or empty-state headers)**: Fraunces (italic, optical size auto)
- **Code, policy IDs, claim numbers and currency amounts**: Geist Mono (`font-variant-numeric: tabular-nums`)

## Colors

- **Primary (Brand & active actions)**: Electric Indigo `#6366F1` (hover `#4F46E5`), white text
- **Secondary (Approved / positive state)**: Jade Emerald `#10B981`, Obsidian `#090D16` text on fills; darkened to `#047857` for text on light surfaces
- **Tertiary (Pending / waiting for sign-off / warning)**: Amber Gold `#F59E0B`, Obsidian `#090D16` text on fills; darkened to `#B45309` for text on light surfaces
- **Information (In progress / referred / neutral state)**: Sky Cyan `#0EA5E9`, white text on fills; darkened to `#0369A1` for text on light surfaces
- **Highlight or alert (Declined / security flag / destructive)**: Crimson Rose `#F43F5E`, white text
- **Ink on light backgrounds**: Obsidian Slate `#0F172A` (primary), Muted Slate `#475569` (secondary)
- **Ink on dark backgrounds**: Polar Mist `#F1F5F9` (primary), Cool Ash `#94A3B8` (secondary)

When three things sit side by side, such as a claim's states or chart series, use Jade Emerald, Amber Gold and Sky Cyan. Add Electric Indigo fourth and Crimson Rose fifth. Status badges pair a soft 12%-opacity tint background with a 1px semantic border and high-contrast label text, always showing both a color and a word.

## Surfaces

- **Light mode**:
  - Page canvas: Cool Alabaster `#F8FAFC`
  - Elevated panels, tables and cards: Pure White `#FFFFFF` with a `1px solid #E2E8F0` hairline border and subtle ambient shadow (`0 1px 3px rgba(15, 23, 42, 0.04)`)
  - Subtle inset / code / diff wells: `#F1F5F9`
- **Dark mode**:
  - Page canvas: Deep Obsidian `#090D16`
  - Elevated panels, tables and cards: Midnight Graphite `#111827` with a `1px solid #1E293B` hairline border and top inner highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.04)`)
  - Subtle inset / code / diff wells: `#0D131F`

Panels use a crisp `10px` border radius (`6px` for buttons, inputs and status pills). Keep interactive focus rings unmistakable (`2px solid #6366F1` with `2px` offset).

## Layout & Micro-Interactions

- **Density & alignment**: Generous breathing room (`24px` panel padding, `16px` grid gaps) paired with compact, scannable data tables. Always right-align currency amounts and numeric columns using tabular numerals (`Geist Mono`).
- **Motion**: Fast, purposeful transitions (`150ms cubic-bezier(0.16, 1, 0.3, 1)`) for hover states, drawers and status updates. Layout must never shift or jump when live data refreshes.

## Avoid

- Thick colored side-stripe borders on cards or neon glow shadows
- Heavy multi-stop background gradients that compete with data legibility
- Pure `#000000` backgrounds in dark mode or unstyled default browser inputs
- Emojis anywhere in the interface

## Tone

Plain business English in US spelling. Short labels, no jargon and no exclamation marks. Money is in US dollars, such as $1,250.00.
