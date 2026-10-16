import { chartOptionsFromToolCalls } from '@/types/analysis'
import type { ToolCallRecord } from '@/types/analysis'
import { describe, expect, it } from 'vitest'

const agg = (args: Record<string, unknown>, result: Record<string, unknown> = {}): ToolCallRecord => ({
  tool: 'group_by_aggregate',
  arguments: args,
  result,
})

describe('chartOptionsFromToolCalls', () => {
  it('maps a group_by_aggregate call to the exact query it ran', () => {
    expect(chartOptionsFromToolCalls([agg({ group_by: ['region'], column: 'revenue', op: 'sum' })])).toEqual([
      {
        label: 'sum of revenue by region',
        query: {
          group_by: ['region'],
          aggregations: [{ op: 'sum', column: 'revenue', alias: 'value' }],
          sort_by: 'value',
          sort_desc: true,
        },
      },
    ])
  })

  it('ranks breakdowns, then columns the question mentions, then the latest call', () => {
    const labels = chartOptionsFromToolCalls(
      [
        agg({ group_by: ['region'], column: 'revenue', op: 'sum' }),
        agg({ group_by: [], column: 'revenue', op: 'sum' }),
        agg({ group_by: ['region'], column: 'order_id', op: 'count' }),
      ],
      'What is the total revenue per region?',
    ).map((o) => o.label)
    expect(labels).toEqual(['sum of revenue by region', 'count of order_id by region', 'sum of revenue (total)'])
  })

  it('skips failed calls, duplicates, and tools that are not one chartable query', () => {
    const options = chartOptionsFromToolCalls([
      agg({ group_by: ['x'], op: 'sum' }, { error: 'no column x' }),
      agg({ group_by: ['a'], op: 'count' }),
      agg({ group_by: ['a'], op: 'count' }),
      { tool: 'get_dataset_profile', arguments: {}, result: {} },
    ])
    expect(options.map((o) => o.label)).toEqual(['count of rows by a'])
    expect(chartOptionsFromToolCalls([])).toEqual([])
  })
})
