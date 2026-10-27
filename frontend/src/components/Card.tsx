import { useDraggable } from '@dnd-kit/core'
import type { Application } from '../api/types'
import { ago, daysAgo, daysUntil } from '../lib/dates'
import { JOB_TYPE_LABEL } from '../lib/status'

type Props = { application: Application; onOpen?: (id: string) => void; overlay?: boolean }

export function Card({ application: a, onOpen, overlay = false }: Props) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: a.id, disabled: overlay })
  const due = daysUntil(a.deadline)
  const dueSoon = due !== null && due >= 0 && due <= 7 && (a.status === 'wishlist' || a.status === 'assessment')
  const dragProps = overlay ? {} : { ref: setNodeRef, ...listeners, ...attributes }

  return (
    <div
      {...dragProps}
      onClick={() => onOpen?.(a.id)}
      className={`cursor-grab rounded-lg border border-stone-200 bg-white p-3 text-left shadow-xs transition hover:border-stone-300 hover:shadow-sm active:cursor-grabbing ${
        isDragging ? 'opacity-40' : ''
      } ${overlay ? 'rotate-2 shadow-lg' : ''}`}
    >
      <div className="truncate font-semibold">{a.company}</div>
      <div className="truncate text-sm text-stone-600">{a.role}</div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-stone-500">
        {a.job_type && <span className="rounded bg-stone-100 px-1.5 py-0.5">{JOB_TYPE_LABEL[a.job_type]}</span>}
        {a.location && <span className="truncate">{a.location}</span>}
        <span className="ml-auto whitespace-nowrap">{a.applied_at ? daysAgo(a.applied_at) : ago(a.created_at)}</span>
      </div>
      {dueSoon && (
        <div className="mt-2 text-xs font-medium text-rose-600">
          {due === 0 ? 'Due today' : `Due in ${due} day${due === 1 ? '' : 's'}`}
        </div>
      )}
    </div>
  )
}
