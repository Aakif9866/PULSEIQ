import { CHART_CHROME, CHART_SERIES_COLORS } from '@/lib/chart-theme'
import type { ChartType } from '@/types/dashboard'
import type { DatasetQueryResult } from '@/types/dataset'
import type { EChartsOption } from 'echarts'

/** Builds an ECharts option from a query result. The first column is
 * always the category axis; every remaining column is its own series,
 * sharing one y-axis (never dual-axis — see dataviz skill anti-patterns).
 * Colors are assigned by fixed slot order, never cycled or re-picked. */
export function buildChartOption(result: DatasetQueryResult, chartType: ChartType): EChartsOption {
  const [categoryColumn, ...seriesColumns] = result.columns
  const categories = result.rows.map((row) => String(row[0] ?? ''))
  const showLegend = seriesColumns.length >= 2

  const series = seriesColumns.map((name, index) => {
    const columnIndex = index + 1
    const data = result.rows.map((row) => row[columnIndex] as number)
    const color = CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length]

    return chartType === 'line'
      ? {
          name,
          type: 'line' as const,
          data,
          color,
          lineStyle: { width: 2 },
          symbol: 'circle',
          symbolSize: 8,
        }
      : {
          name,
          type: 'bar' as const,
          data,
          color,
          barMaxWidth: 24,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
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
      axisPointer: { type: chartType === 'line' ? 'line' : 'shadow' },
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
