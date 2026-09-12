import { CHART_CHROME, CHART_SERIES_COLORS } from '@/lib/chart-theme'
import type { ChartType } from '@/types/dashboard'
import type { DatasetQueryResult } from '@/types/dataset'
import type { EChartsOption } from 'echarts'

const MAX_PIE_SLICES = 6

/** Builds an ECharts option from a query result. `kpi` and `table` chart
 * types never reach this function — they're rendered as plain React
 * components (KpiCard / ResultTable) instead, since neither is really a
 * "chart" in the ECharts sense. See dataviz skill: a single headline
 * number is a stat tile, not a chart. */
export function buildChartOption(result: DatasetQueryResult, chartType: ChartType): EChartsOption {
  if (chartType === 'pie') {
    return buildPieOption(result)
  }
  if (chartType === 'scatter') {
    return buildScatterOption(result)
  }
  return buildCartesianOption(result, chartType as 'bar' | 'line' | 'area')
}

function buildCartesianOption(
  result: DatasetQueryResult,
  chartType: 'bar' | 'line' | 'area',
): EChartsOption {
  const [categoryColumn, ...seriesColumns] = result.columns
  const categories = result.rows.map((row) => String(row[0] ?? ''))
  const showLegend = seriesColumns.length >= 2

  const series = seriesColumns.map((name, index) => {
    const columnIndex = index + 1
    const data = result.rows.map((row) => row[columnIndex] as number)
    const color = CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length]

    if (chartType === 'bar') {
      return {
        name,
        type: 'bar' as const,
        data,
        color,
        barMaxWidth: 24,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      }
    }
    // line and area share the same series shape — area is just a line
    // with its fill turned on, never a second y-axis (see dataviz skill:
    // one axis, always).
    return {
      name,
      type: 'line' as const,
      data,
      color,
      lineStyle: { width: 2 },
      symbol: 'circle',
      symbolSize: 8,
      areaStyle: chartType === 'area' ? { opacity: 0.18 } : undefined,
    }
  })

  return {
    color: [...CHART_SERIES_COLORS],
    textStyle: { color: CHART_CHROME.axisLabel, fontFamily: 'inherit' },
    grid: { left: 48, right: 16, top: showLegend ? 36 : 16, bottom: 32 },
    legend: showLegend
      ? { show: true, textStyle: { color: CHART_CHROME.axisLabel }, top: 0 }
      : { show: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: chartType === 'bar' ? 'shadow' : 'line' },
      backgroundColor: CHART_CHROME.tooltipBg,
      borderColor: CHART_CHROME.tooltipBorder,
      textStyle: { color: CHART_CHROME.tooltipText },
    },
    xAxis: {
      type: 'category',
      name: categoryColumn,
      data: categories,
      axisLine: { lineStyle: { color: CHART_CHROME.axisLine } },
      axisLabel: { color: CHART_CHROME.axisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: CHART_CHROME.axisLabel },
      splitLine: { lineStyle: { color: CHART_CHROME.splitLine } },
    },
    series,
  }
}

/** A scatter plot needs two genuinely numeric axes, not a category axis —
 * the first column is treated as x, the second as y. Extra columns beyond
 * that aren't plotted (a scatter of >2 dimensions needs a different
 * encoding entirely, out of scope here). */
function buildScatterOption(result: DatasetQueryResult): EChartsOption {
  const [xColumn, yColumn] = result.columns
  const points = result.rows.map((row) => [Number(row[0]), Number(row[1])])

  return {
    color: [CHART_SERIES_COLORS[0]],
    textStyle: { color: CHART_CHROME.axisLabel, fontFamily: 'inherit' },
    grid: { left: 48, right: 16, top: 16, bottom: 32 },
    tooltip: {
      trigger: 'item',
      backgroundColor: CHART_CHROME.tooltipBg,
      borderColor: CHART_CHROME.tooltipBorder,
      textStyle: { color: CHART_CHROME.tooltipText },
    },
    xAxis: {
      type: 'value',
      name: xColumn,
      axisLine: { lineStyle: { color: CHART_CHROME.axisLine } },
      axisLabel: { color: CHART_CHROME.axisLabel },
      splitLine: { lineStyle: { color: CHART_CHROME.splitLine } },
    },
    yAxis: {
      type: 'value',
      name: yColumn,
      axisLine: { show: false },
      axisLabel: { color: CHART_CHROME.axisLabel },
      splitLine: { lineStyle: { color: CHART_CHROME.splitLine } },
    },
    series: [
      {
        type: 'scatter',
        data: points,
        symbolSize: 10,
        itemStyle: { color: CHART_SERIES_COLORS[0] },
      },
    ],
  }
}

/** A pie only ever shows the first series column, as a part-to-whole
 * breakdown of the category column — never a comparison of close values
 * or a 2-slice split (see dataviz skill anti-patterns), so more than
 * MAX_PIE_SLICES categories fold into "Other" rather than rendering an
 * unreadable wheel of thin slivers. */
function buildPieOption(result: DatasetQueryResult): EChartsOption {
  const rows = result.rows.map((row) => ({ name: String(row[0] ?? ''), value: Number(row[1]) }))
  rows.sort((a, b) => b.value - a.value)

  const visible = rows.slice(0, MAX_PIE_SLICES)
  const rest = rows.slice(MAX_PIE_SLICES)
  if (rest.length > 0) {
    visible.push({ name: 'Other', value: rest.reduce((sum, r) => sum + r.value, 0) })
  }

  return {
    color: [...CHART_SERIES_COLORS],
    textStyle: { color: CHART_CHROME.axisLabel, fontFamily: 'inherit' },
    legend: {
      show: true,
      orient: 'vertical',
      right: 8,
      top: 'middle',
      textStyle: { color: CHART_CHROME.axisLabel },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: CHART_CHROME.tooltipBg,
      borderColor: CHART_CHROME.tooltipBorder,
      textStyle: { color: CHART_CHROME.tooltipText },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'], // a donut, not a filled disc — easier to compare adjacent slices
        center: ['38%', '50%'],
        data: visible,
        itemStyle: {
          borderColor: CHART_CHROME.tooltipBg,
          borderWidth: 2,
        },
        label: { color: CHART_CHROME.axisLabel },
        labelLine: { lineStyle: { color: CHART_CHROME.axisLine } },
      },
    ],
  }
}
