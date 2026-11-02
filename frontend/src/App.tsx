import { useEffect, useRef, useState } from 'react'
import { ApplicationTable } from './components/ApplicationTable'
import { Board } from './components/Board'
import { DetailDrawer } from './components/DetailDrawer'
import { ProfileModal } from './components/ProfileModal'
import { QuickAddModal } from './components/QuickAddModal'
import { StatsStrip } from './components/StatsStrip'
import { useApplications } from './hooks/useApplications'

type View = 'board' | 'table'

const VIEW_KEY = 'job-tracker:view'

function loadView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'board'
  } catch {
    return 'board'
  }
}

export default function App() {
  const { data: applications = [], isLoading, error } = useApplications()
  const [view, setView] = useState<View>(loadView)
  const [search, setSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const [editingProfile, setEditingProfile] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view)
    } catch {
      // storage unavailable; the view just won't be remembered
    }
  }, [view])

  // Keyboard shortcuts: N = new application, / = search, Esc = close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLElement && e.target.closest('input, textarea, select')
      if (e.key === 'Escape') {
        setAdding(false)
        setEditingProfile(false)
        setOpenId(null)
      } else if (!typing && e.key.toLowerCase() === 'n' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        setAdding(true)
      } else if (!typing && e.key === '/') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const term = search.trim().toLowerCase()
  const visible = term
    ? applications.filter((a) =>
        [a.company, a.role, a.location ?? '', a.notes ?? ''].some((v) => v.toLowerCase().includes(term)),
      )
    : applications

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-stone-200 bg-white px-6 py-4">
        <div className="flex flex-wrap items-center gap-x-10 gap-y-4">
          <h1 className="text-lg font-semibold tracking-tight">Job Tracker</h1>
          <StatsStrip />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <div className="flex rounded-lg bg-stone-100 p-0.5 text-sm">
            {(['board', 'table'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-md px-3 py-1 capitalize ${view === v ? 'bg-white font-medium shadow-xs' : 'text-stone-500'}`}
              >
                {v}
              </button>
            ))}
          </div>
          <input
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company, role, location…  ( / )"
            className="w-72 max-w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-stone-500"
          />
          <button
            onClick={() => setEditingProfile(true)}
            className="ml-auto rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100"
          >
            Profile
          </button>
          <button
            onClick={() => setAdding(true)}
            className="rounded-lg bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700"
          >
            + Add application <kbd className="ml-1 text-xs text-stone-400">N</kbd>
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1 p-4">
        {isLoading && <p className="text-sm text-stone-500">Loading…</p>}
        {error && (
          <p className="text-sm text-rose-600">
            Couldn't reach the API ({error.message}). Is the backend running on port 8000?
          </p>
        )}
        {isLoading || error ? null : applications.length === 0 ? (
          <div className="mx-auto mt-24 max-w-sm text-center">
            <p className="text-lg font-medium">No applications yet</p>
            <p className="mt-1 text-sm text-stone-500">Press N or click below to add the first one.</p>
            <button
              onClick={() => setAdding(true)}
              className="mt-4 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700"
            >
              Add application
            </button>
          </div>
        ) : view === 'board' ? (
          <Board applications={visible} onOpen={setOpenId} />
        ) : (
          <ApplicationTable applications={visible} onOpen={setOpenId} />
        )}
      </main>

      {adding && <QuickAddModal onClose={() => setAdding(false)} />}
      {editingProfile && <ProfileModal onClose={() => setEditingProfile(false)} />}
      {openId && <DetailDrawer id={openId} onClose={() => setOpenId(null)} onOpenProfile={() => setEditingProfile(true)} />}
    </div>
  )
}
