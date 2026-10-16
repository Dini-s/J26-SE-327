# Design tokens (from docs/ui/c1_mockup.png)

The values below were read by eye from the 1920 x 1338 mockup, not measured with a colour picker, so treat them as close approximations. They are the Tailwind theme in `tailwind.config.js`.

## Typography
| Use | Value |
|---|---|
| Font | Inter (self-hosted with `@fontsource/inter`, weights 400/500/600/700; no CDN) |
| Page title "Requirement Intelligence" | 40px (34px below 1280px), weight 500, tight tracking, colour `ink` #0f1330 |
| Panel titles ("Requirement intelligence findings", "Requirement analysis") | 19px, weight 500 |
| Body | 14px, colour `ink.body` #4b5272; row text 13.5px `ink` |
| Small caps labels ("CURRENT PROJECT", "ORIGINAL REQUIREMENT", ...) | 10.5px, weight 600, uppercase, letter-spacing 0.08em, colour `ink.muted` #8a90ab |
| Source line under a row | 10.5px, `ink.faint` #aab0c6 |
| Badges | 10.5px, weight 700 |

## Colours
| Token | Hex | Where |
|---|---|---|
| `page` | #f7f8fc | page background |
| `line` | #e6e8f2 | card and divider borders |
| `ink` / `ink.body` / `ink.muted` / `ink.faint` | #0f1330 / #4b5272 / #8a90ab / #aab0c6 | headings / text / labels / faint text |
| `brand.600` (primary) | #4f46e5 | "Run analysis", REQ ids, selected-row accent, active pipeline step |
| `brand.700` | #4338ca | primary hover |
| `brand.50` / `brand.100` | #eef0ff / #e2e5ff | selected row, step badges, icon tint |
| `nav.bg` | #0c1131 | sidebar background |
| `nav.card` / `nav.line` | #151b3f / #252c5c | project card, dividers |
| `nav.active` | #272f6e | active module background (3px left accent `nav.accent` #6366f1) |
| `nav.text` / `nav.muted` | #c3c9e6 / #7d86b8 | module text / section label |
| Brand mark | gradient #4f46e5 to violet-600 | "{ }" logo tile |
| HIGH badge | bg #fdecec, text #c62828, border #f6c9c9 | `risk.high*` |
| MEDIUM badge | bg #fff6dc, text #a16207, border #f1dd9b | `risk.med*` |
| LOW badge | bg #e8f8ee, text #15803d, border #bde5cb | `risk.low*` |
| NONE badge (not in the mockup) | bg #f1f2f7, text #5b6280, border #dde0ec | `risk.none*` |
| Green banner "C1 owns" | bg #effaf3, border #b7e8c8, text #14532d | `ok` |
| Blue banner "C3 owns next", draft card, boundary card | bg #eef4ff, border #c7dafe, text #1e3a8a | `info` |
| Explanation card | bg #f6f3ff, border #e0d8ff, title #6d28d9, text #5b3fd0 | `ai` |
| Weak-word highlight | bg #fee2e2, text #b91c1c, bold | `hit` |
| Stat card icon tints | indigo #eef0ff/#4f46e5, amber-50/600, red-50/600, violet-50/600, emerald-50/600 | five stat cards |
| Status dots | green #22c55e (ready), amber (generation offline), red (error) | header pill |

## Shape, shadow, spacing
- Card radius 14px (`rounded-card`), controls and inputs 10px (`rounded-ctl`), pills and badges fully rounded.
- Card shadow `0 1px 2px rgba(15,19,48,.04), 0 4px 14px rgba(15,19,48,.04)`, 1px border `line`, white background.
- Page gutters 36px at 1280px and wider (24px below), 20px between cards, card padding 16-24px, rows 14px vertical padding.
- Sidebar 280px wide (72px icon rail below 1024px); breakpoint `xl` (1280px) is where the findings list and the detail panel sit side by side and the five stat cards fit in one row.
- Selected list row: `brand.50` background with a 3px `brand.600` left border.
