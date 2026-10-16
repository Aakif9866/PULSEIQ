/**
 * Chart color tokens for PulseIQ (light and dark).
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

/** Chart chrome per theme — mirrors the --color-* tokens in index.css so a
 * chart reads as part of the app. ECharts needs literal values, not CSS
 * custom properties, so charts re-render when the theme flips. */
export const CHART_CHROME = {
  dark: {
    axisLine: '#3a3a3c', // --color-border-strong
    splitLine: '#2c2c2e', // --color-border
    axisLabel: '#a1a1a6', // --color-fg-muted
    tooltipBg: '#2c2c2e', // --color-surface-raised
    tooltipBorder: '#3a3a3c',
    tooltipText: '#f5f5f7', // --color-fg
    sliceBorder: '#1c1c1e', // --color-surface
  },
  light: {
    axisLine: '#d1d1d6',
    splitLine: '#e5e5ea',
    axisLabel: '#6e6e73',
    tooltipBg: '#ffffff',
    tooltipBorder: '#d1d1d6',
    tooltipText: '#1d1d1f',
    sliceBorder: '#ffffff',
  },
} as const
