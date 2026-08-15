# THREADLINE design system

## Brand idea

THREADLINE is calm infrastructure for difficult decisions. Its visual language combines humanitarian editorial clarity, inspectable evidence, and restrained operational depth. Light indicates provenance and state; it is never ornamental noise.

## Color tokens

| Role | Value | Use |
|---|---|---|
| Main background | `#07131F` | page and deep workspace field |
| Raised surface | `#0B1E2D` | cards, panels, dialogs |
| Elevated surface | `#102838` | selected rows, toolbars, controls |
| Primary cyan | `#49C9D8` | supporting thread, primary action, focus associations |
| Soft cyan | `#9BE7ED` | focus ring, emphasized text, selected evidence |
| Verified mint | `#7ED9BD` | passed deterministic rule / intact provenance |
| Review amber | `#F1C66D` | unresolved gap, review requirement, estimated time |
| Blocked coral | `#F47F7F` | hard contradiction, invalid claim, withheld release |
| Primary text | `#F3F7F8` | headings and essential values |
| Secondary text | `#B8C7CD` | body and explanations |
| Muted text | `#91A5AE` | metadata with AA-aware sizing |
| Divider | `rgba(155, 231, 237, 0.12)` | subtle surface separation |

Color is always paired with text, icon geometry, line style, or status label. Supporting edges are solid cyan; unresolved edges amber with a spaced dash; blocked edges coral with a break marker; incomplete edges muted and dotted.

## Typography

- **Interface:** `Manrope`, falling back to `Avenir Next`, `Segoe UI Variable`, `Segoe UI`, and sans-serif. No remote font fetch is required.
- **Evidence:** `IBM Plex Mono`, falling back to `Cascadia Code`, `SFMono-Regular`, Consolas, and monospace.
- Display headings use the interface family at 560–650 weight; the product does not use a separate editorial serif.
- Minimum normal body size is 14px in dense workspace panels and 16px in landing copy. Only IDs/offsets/captions may descend to 11px, with strong contrast and generous tracking.

## Type scale

- Hero: `clamp(3rem, 7.5vw, 7rem)`, line-height 0.94.
- Page title: `clamp(2rem, 4vw, 3.75rem)`.
- Section title: `clamp(1.5rem, 2.8vw, 2.6rem)`.
- Panel title: 16–20px.
- Body: 15–18px, line-height 1.55–1.7.
- Operational metadata: 11–12px mono, uppercase only for short labels.

## Spacing and shape

- Base spatial unit: 4px; common steps: 8, 12, 16, 24, 32, 48, 64, 96.
- Content width: 1440px maximum with 16–32px gutters.
- Corners: 6px controls, 10px panels, 16px feature surfaces. Avoid giant pills; status chips are the only fully rounded form.
- Borders: one pixel with explicit surface contrast; a 2–3px accent edge is reserved for release state.
- Shadows: low-opacity black depth plus at most one subtle cyan ambient bloom on hero/evidence focus.

## Surfaces and texture

- Use layered solid dark surfaces with visible separation.
- Document panels may add a very low-opacity paper fiber/noise texture made locally with CSS gradients or a repository-owned SVG filter.
- Glass blur is limited to sticky navigation/dialog backdrops and must retain an opaque fallback.
- Grid texture is functional in evidence canvases only.

## Motion

- Standard transition: 140–180ms, ease-out.
- Evidence travel: 320–520ms with a single path-reveal and destination emphasis.
- Pointer parallax: maximum 6px translation, requestAnimationFrame throttled, no rotation, no autonomous drift.
- Guided demo: user-advanced by default; optional timed progression stops on interaction and never runs under reduced motion.
- `prefers-reduced-motion: reduce` makes the final evidence path fully visible, removes parallax/auto-advance/pulse, and retains all state changes instantly.

## Controls

Every important action supports:

- default: visible label and stable border;
- hover: small luminance/border change;
- focus: 2px soft-cyan ring with 3px offset;
- pressed: 1px translate or inset treatment;
- loading: stable width, spinner plus live text, and `aria-busy`;
- disabled: reduced contrast with `not-allowed`, never hidden reason;
- success: mint edge and explicit success copy;
- warning: amber edge and remediation text;
- failure: coral edge and retry/recovery action.

Primary workflow labels are fixed: `Run Evidence Contract`, `Validating Evidence…`, `Resolve Contract Violations`, `Send to Authorized Review`, `Record Authorized Decision`.

## Accessibility

- WCAG AA contrast target; focus and status never rely on color alone.
- Minimum interactive target 44×44px where layout permits; graph nodes use 40px minimum plus surrounding hit area.
- Semantic landmarks, headings, lists, tables, definitions, figures, and native dialogs.
- Keyboard graph travel follows DOM order and supports Tab/Shift+Tab; arrow keys are additive, never required.
- Dialog focus restores to the invoking control.
- Live announcements are concise and use polite regions except release blocking, which is assertive.
- Arabic source text retains `lang="ar"` and `dir="rtl"`; translation is a separate attributed representation.
- Every SVG evidence/map/chart has a concise accessible name and nearby text equivalent.

## Content rules

- Never imply identity certainty or outcome probability.
- Scores are evidence-priority aids only when their formula and uncertainty are visible.
- Use specific nouns: source span, record, contradiction, rival, contract rule, audit event.
- Avoid fake metrics, fake code, unexplained acronyms, and decorative status language.
