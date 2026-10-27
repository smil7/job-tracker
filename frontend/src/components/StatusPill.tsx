import type { Status } from '../api/types'
import { STATUS_META } from '../lib/status'

export function StatusPill({ status }: { status: Status }) {
  const meta = STATUS_META[status]
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta.pill}`}>
      {meta.label}
    </span>
  )
}
