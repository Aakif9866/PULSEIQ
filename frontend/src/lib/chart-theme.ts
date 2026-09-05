/**
 * Chart color tokens for PulseIQ's dark-only surface.
 *
 * These are the dataviz-skill reference categorical palette's dark steps,
 * validated (scripts/validate_palette.js --mode dark --surface #101114,
 * matching --color-surface) against this app's actual card background —
 * all 8 slots pass lightness/chroma/CVD/contrast. Assign by fixed index
 * order, never cycle or reassign based on a filter.
 */
export const CHART_SERIES_COLORS = [
  '#3987e5', // 1 blue
  '#d95926', // 2 orange
  '#199e70', // 3 aqua
  '#c98500', // 4 yellow
  '#d55181', // 5 magenta
  '#008300', // 6 green
  '#9085e9', // 7 violet
  '#e66767', // 8 red
] as const

/** Chart chrome — matches this app's own --color-* tokens (index.css) so a
 * chart reads as part of the app, not a pasted-in widget. Canvas-rendered,
 * so these must be literal values, not CSS custom properties. */
export const CHART_CHROME = {
  axisLine: '#34363c', // --color-border-strong
  splitLine: '#24262b', // --color-border
  axisLabel: '#9a9da5', // --color-fg-muted
  tooltipBg: '#16181c', // --color-surface-raised
  tooltipBorder: '#24262b', // --color-border
  tooltipText: '#e7e8ea', // --color-fg
} as const
