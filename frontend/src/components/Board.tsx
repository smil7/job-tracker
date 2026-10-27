import { DndContext, DragOverlay, PointerSensor, useDroppable, useSensor, useSensors } from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import { useState } from 'react'
import type { Application, Status } from '../api/types'
import { useUpdateApplication } from '../hooks/useApplications'
import { CLOSED_STATUSES, OPEN_STATUSES, STATUS_META } from '../lib/status'
import { Card } from './Card'

type Props = { applications: Application[]; onOpen: (id: string) => void }

export function Board({ applications, onOpen }: Props) {
  const update = useUpdateApplication()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [showClosed, setShowClosed] = useState(false)
  // A small drag threshold keeps plain clicks working for opening the drawer
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const byStatus = (status: Status) => applications.filter((a) => a.status === status)
  const active = applications.find((a) => a.id === activeId)

  const onDragStart = (e: DragStartEvent) => setActiveId(String(e.active.id))
  const onDragEnd = (e: DragEndEvent) => {
    setActiveId(null)
    const target = e.over?.id as Status | undefined
    const app = applications.find((a) => a.id === e.active.id)
    if (app && target && target !== app.status) update.mutate({ id: app.id, body: { status: target } })
  }

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActiveId(null)}>
      <div className="flex h-full gap-3 overflow-x-auto pb-2">
        {OPEN_STATUSES.map((status) => (
          <Column key={status} status={status} applications={byStatus(status)} onOpen={onOpen} />
        ))}
        {showClosed ? (
          <>
            {CLOSED_STATUSES.map((status) => (
              <Column key={status} status={status} applications={byStatus(status)} onOpen={onOpen} />
            ))}
            <button
              onClick={() => setShowClosed(false)}
              className="h-fit shrink-0 rounded-lg px-2 py-1 text-xs whitespace-nowrap text-stone-500 hover:bg-stone-200"
            >
              Hide closed
            </button>
          </>
        ) : (
          <div className="flex w-40 shrink-0 flex-col gap-2">
            {CLOSED_STATUSES.map((status) => (
              <CollapsedColumn key={status} status={status} count={byStatus(status).length} />
            ))}
            <button
              onClick={() => setShowClosed(true)}
              className="rounded-lg px-2 py-1 text-xs text-stone-500 hover:bg-stone-200"
            >
              Show closed
            </button>
          </div>
        )}
      </div>
      {/* No drop animation: the card has already moved (optimistic update), so animating back looks wrong */}
      <DragOverlay dropAnimation={null}>{active ? <Card application={active} overlay /> : null}</DragOverlay>
    </DndContext>
  )
}

type ColumnProps = { status: Status; applications: Application[]; onOpen: (id: string) => void }

function Column({ status, applications, onOpen }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  const meta = STATUS_META[status]
  return (
    <section
      ref={setNodeRef}
      className={`flex w-72 shrink-0 flex-col rounded-xl p-2 transition-colors ${isOver ? 'bg-stone-300/70' : 'bg-stone-200/60'}`}
    >
      <header className="flex items-center gap-2 px-1 pt-1 pb-2 text-sm font-medium">
        <span className={`size-2 rounded-full ${meta.dot}`} />
        {meta.label}
        <span className="text-stone-500 tabular-nums">{applications.length}</span>
      </header>
      <div className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto">
        {applications.map((a) => (
          <Card key={a.id} application={a} onOpen={onOpen} />
        ))}
      </div>
    </section>
  )
}

// Rejected / Withdrawn stay droppable while hidden
function CollapsedColumn({ status, count }: { status: Status; count: number }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  const meta = STATUS_META[status]
  return (
    <div
      ref={setNodeRef}
      className={`flex items-center gap-2 rounded-xl border border-dashed px-3 py-4 text-sm transition-colors ${
        isOver ? 'border-stone-500 bg-stone-300/70' : 'border-stone-300 bg-stone-200/40'
      }`}
    >
      <span className={`size-2 rounded-full ${meta.dot}`} />
      {meta.label}
      <span className="ml-auto text-stone-500 tabular-nums">{count}</span>
    </div>
  )
}
