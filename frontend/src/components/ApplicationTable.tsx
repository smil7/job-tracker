import { useState } from 'react'
import type { Application } from '../api/types'
import { ago, formatDay } from '../lib/dates'
import { JOB_TYPE_LABEL, STATUSES } from '../lib/status'
import { StatusPill } from './StatusPill'

type SortKey = 'company' | 'role' | 'status' | 'job_type' | 'location' | 'applied_at' | 'deadline' | 'updated_at'

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'company', label: 'Company' },
  { key: 'role', label: 'Role' },
  { key: 'status', label: 'Stage' },
  { key: 'job_type', label: 'Type' },
  { key: 'location', label: 'Location' },
  { key: 'applied_at', label: 'Applied' },
  { key: 'deadline', label: 'Deadline' },
  { key: 'updated_at', label: 'Updated' },
]

function sortValue(a: Application, key: SortKey): string | number {
  // Stages sort in pipeline order rather than alphabetically
  if (key === 'status') return STATUSES.indexOf(a.status)
  return (a[key] ?? '').toLowerCase()
}

export function ApplicationTable({ applications, onOpen }: { applications: Application[]; onOpen: (id: string) => void }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'updated_at', desc: true })

  const sorted = [...applications].sort((a, b) => {
    const x = sortValue(a, sort.key)
    const y = sortValue(b, sort.key)
    if (x === y) return 0
    // Empty values always go last
    if (x === '') return 1
    if (y === '') return -1
    return (x < y ? -1 : 1) * (sort.desc ? -1 : 1)
  })

  const toggle = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key.endsWith('_at') }))

  return (
    <div className="h-full overflow-auto rounded-xl border border-stone-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-stone-50 text-xs text-stone-500">
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className="border-b border-stone-200 px-3 py-2 font-medium whitespace-nowrap">
                <button onClick={() => toggle(c.key)} className="hover:text-stone-900">
                  {c.label}
                  {sort.key === c.key && <span className="ml-1">{sort.desc ? '↓' : '↑'}</span>}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr
              key={a.id}
              onClick={() => onOpen(a.id)}
              className="cursor-pointer border-b border-stone-100 last:border-0 hover:bg-stone-50"
            >
              <td className="px-3 py-2 font-medium">{a.company}</td>
              <td className="px-3 py-2">{a.role}</td>
              <td className="px-3 py-2">
                <StatusPill status={a.status} />
              </td>
              <td className="px-3 py-2 text-stone-600">{a.job_type ? JOB_TYPE_LABEL[a.job_type] : '—'}</td>
              <td className="px-3 py-2 text-stone-600">{a.location ?? '—'}</td>
              <td className="px-3 py-2 whitespace-nowrap text-stone-600">{formatDay(a.applied_at)}</td>
              <td className="px-3 py-2 whitespace-nowrap text-stone-600">{formatDay(a.deadline)}</td>
              <td className="px-3 py-2 whitespace-nowrap text-stone-500">{ago(a.updated_at)}</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={COLUMNS.length} className="px-3 py-10 text-center text-stone-500">
                Nothing here yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
