import { format, parseISO } from 'date-fns'
import { useState } from 'react'
import type { FormEvent } from 'react'
import type { ApplicationDetail, Status, StatusEvent } from '../api/types'
import { useAddNote, useApplication, useDeleteApplication, useUpdateApplication } from '../hooks/useApplications'
import { fromApplication, toBody } from '../lib/form'
import { STATUS_META, STATUSES } from '../lib/status'
import { AiGate } from './AiGate'
import { CoverLetterPanel } from './CoverLetterPanel'
import { FormFields, inputClass } from './FormFields'
import { ResumeReviewPanel } from './ResumeReviewPanel'

type Tab = 'details' | 'review' | 'letter'

const TABS: { id: Tab; label: string }[] = [
  { id: 'details', label: 'Details' },
  { id: 'review', label: 'Resume review' },
  { id: 'letter', label: 'Cover letter' },
]

export function DetailDrawer({
  id,
  onClose,
  onOpenProfile,
}: {
  id: string
  onClose: () => void
  onOpenProfile: () => void
}) {
  const { data, isLoading, error } = useApplication(id)

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-stone-900/20" onMouseDown={onClose}>
      <aside
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-xl flex-col overflow-y-auto bg-white shadow-2xl"
      >
        {isLoading && <p className="p-6 text-sm text-stone-500">Loading…</p>}
        {error && <p className="p-6 text-sm text-rose-600">{error.message}</p>}
        {/* key resets the form when the drawer switches to another application */}
        {data && <DrawerBody key={data.id} application={data} onClose={onClose} onOpenProfile={onOpenProfile} />}
      </aside>
    </div>
  )
}

function DrawerBody({
  application,
  onClose,
  onOpenProfile,
}: {
  application: ApplicationDetail
  onClose: () => void
  onOpenProfile: () => void
}) {
  const update = useUpdateApplication()
  const remove = useDeleteApplication()
  const [tab, setTab] = useState<Tab>('details')
  const [form, setForm] = useState(() => fromApplication(application))
  const dirty = JSON.stringify(form) !== JSON.stringify(fromApplication(application))

  const save = (e: FormEvent) => {
    e.preventDefault()
    update.mutate({ id: application.id, body: toBody(form) })
  }

  const setStatus = (status: Status) =>
    update.mutate(
      { id: application.id, body: { status } },
      // The server fills in the applied date when leaving the wishlist; keep the form in step
      { onSuccess: (d) => setForm((f) => ({ ...f, applied_at: f.applied_at || (d.applied_at ?? '') })) },
    )

  const destroy = () => {
    if (confirm(`Delete ${application.company} – ${application.role}?`)) {
      remove.mutate(application.id, { onSuccess: onClose })
    }
  }

  return (
    <>
      <header className="sticky top-0 z-10 flex items-start gap-3 border-b border-stone-200 bg-white px-6 py-4">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-semibold">{application.company}</h2>
          <p className="truncate text-sm text-stone-600">{application.role}</p>
          {application.job_url && (
            <a
              href={application.job_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-sky-700 hover:underline"
            >
              Open posting ↗
            </a>
          )}
        </div>
        <div className="w-36 shrink-0">
          <select
            aria-label="Stage"
            className={inputClass}
            value={application.status}
            onChange={(e) => setStatus(e.target.value as Status)}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_META[s].label}
              </option>
            ))}
          </select>
        </div>
        <button onClick={onClose} aria-label="Close" className="rounded-md px-2 py-1 text-stone-500 hover:bg-stone-100">
          ✕
        </button>
      </header>

      <nav className="flex gap-1 border-b border-stone-200 px-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === t.id ? 'border-stone-900 font-medium text-stone-900' : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'details' && (
        <>
          <form onSubmit={save} className="px-6 py-5">
            <FormFields form={form} onChange={setForm} />
            {update.error && <p className="mt-3 text-sm text-rose-600">{update.error.message}</p>}
            <div className="mt-4 flex items-center gap-2">
              <button type="button" onClick={destroy} className="text-sm text-rose-600 hover:text-rose-800">
                Delete
              </button>
              <button
                type="submit"
                disabled={!dirty || update.isPending}
                className="ml-auto rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-40"
              >
                Save changes
              </button>
            </div>
          </form>

          <Timeline applicationId={application.id} events={application.events} />
        </>
      )}
      {tab === 'review' && (
        <AiGate application={application} onOpenProfile={onOpenProfile}>
          <ResumeReviewPanel applicationId={application.id} />
        </AiGate>
      )}
      {tab === 'letter' && (
        <AiGate application={application} onOpenProfile={onOpenProfile}>
          <CoverLetterPanel applicationId={application.id} />
        </AiGate>
      )}
    </>
  )
}

function Timeline({ applicationId, events }: { applicationId: string; events: StatusEvent[] }) {
  const addNote = useAddNote()
  const [note, setNote] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!note.trim()) return
    addNote.mutate({ id: applicationId, note: note.trim() }, { onSuccess: () => setNote('') })
  }

  return (
    <section className="border-t border-stone-200 px-6 py-5">
      <h3 className="mb-3 text-sm font-semibold">Timeline</h3>
      <form onSubmit={submit} className="mb-4 flex gap-2">
        <input
          className={inputClass}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add an update, e.g. Recruiter called"
        />
        <button
          type="submit"
          disabled={!note.trim() || addNote.isPending}
          className="rounded-md border border-stone-300 px-3 text-sm hover:bg-stone-100 disabled:opacity-40"
        >
          Add
        </button>
      </form>
      <ol className="relative ml-1.5 border-l border-stone-200">
        {events.map((event) => (
          <li key={event.id} className="mb-4 ml-4">
            <span
              className={`absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-white ${
                event.to_status ? STATUS_META[event.to_status].dot : 'bg-stone-300'
              }`}
            />
            <p className="text-sm">{describe(event)}</p>
            <time className="text-xs text-stone-500">{format(parseISO(event.occurred_at), 'd MMM yyyy, HH:mm')}</time>
          </li>
        ))}
      </ol>
    </section>
  )
}

function describe(event: StatusEvent) {
  if (!event.to_status) return event.note
  const to = STATUS_META[event.to_status].label
  if (!event.from_status) return `${event.note ?? 'Added'} as ${to}`
  return `Moved from ${STATUS_META[event.from_status].label} to ${to}`
}
