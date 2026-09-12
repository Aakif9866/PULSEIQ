import type { DatasetQueryResult } from '@/types/dataset'

interface ResultTableProps {
  result: DatasetQueryResult
}

/** A raw table view of a query result — the "table" chart type, and also
 * the fallback the dataviz skill asks every chart to have available.
 * Numeric columns use tabular-nums so digits align down a column (the
 * opposite rule from KpiCard's single hero number). */
export function ResultTable({ result }: ResultTableProps) {
  return (
    <div className="max-h-64 overflow-auto rounded-md border border-[var(--color-border)]">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 bg-[var(--color-surface-raised)]">
          <tr>
            {result.columns.map((col) => (
              <th
                key={col}
                className="whitespace-nowrap border-b border-[var(--color-border)] px-3 py-2 text-left font-medium text-[var(--color-fg-muted)]"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, rowIndex) => (
            // eslint-disable-next-line react/no-array-index-key -- rows have no stable id
            <tr key={rowIndex} className="border-b border-[var(--color-border)] last:border-b-0">
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="whitespace-nowrap px-3 py-1.5 text-[var(--color-fg)] [font-variant-numeric:tabular-nums]"
                >
                  {String(cell ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {result.rows.length === 0 && (
        <p className="px-3 py-4 text-center text-[var(--color-fg-subtle)]">No rows.</p>
      )}
    </div>
  )
}
