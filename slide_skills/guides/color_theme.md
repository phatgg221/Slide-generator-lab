# Color & Theme Guidance

Rules for choosing a deck's color palette. Followed by the palette-proposing
and planning agents. Keep edits crisp — every line costs prompt tokens.

## Principles
- **Fit the topic, don't default to blue.** The palette should feel chosen for
  THIS subject. If the same colors would suit a totally different deck, they're
  too generic. Finance ≠ wellness ≠ kids' education ≠ luxury.
- **Dominance, not equality.** One color carries 60–70% of the visual weight,
  1–2 support it, one sharp accent. Never weight all colors equally.
- **Preserve contrast / luminance.** Dark text stays dark, light backgrounds
  stay light. Body text must stay readable on its background (WCAG AA: ≥4.5:1).
- **Limit the hue count.** One dominant hue family + one accent. More hues read
  as noise.

## Topic → palette starting points
| Topic feel | Primary (dark) | Secondary (light) | Accent (vivid) |
|---|---|---|---|
| Corporate / finance | navy `1E2761` | ice `CADCFC` | blue `4F6BD8` |
| Tech / AI | charcoal `1A1A2E` | mist `E8E8F0` | electric `00D4FF` |
| Nature / sustainability | forest `2C5F2D` | sand `EAF2E0` | moss `97BC62` |
| Health / calm | slate `2F4858` | cloud `E6EEF2` | teal `02C39A` |
| Energy / bold / sports | ink `1B1B1B` | bone `F4F1EA` | coral `F96167` |
| Luxury / premium | espresso `2B2118` | cream `ECE2D0` | gold `C9A227` |
| Education / friendly | indigo `3A0CA3` | paper `F7F4FF` | amber `FFB703` |
| Warm / artisanal | terracotta `B85042` | sand `E7E8D1` | sage `A7BEAE` |

These are starting points — adapt the exact hues to the specific subject.

## When to keep the template's original colors
If the brief implies a strong existing brand, or the template's palette already
fits the topic, prefer keeping it (return no recolor) over forcing a change.
