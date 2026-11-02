import type { ReactNode } from 'react'
import type { ApplicationDetail } from '../api/types'
import { useProfile } from '../hooks/useApplications'

/** Renders the AI panel only when the resume and the job description it needs exist. */
export function AiGate({
  application,
  onOpenProfile,
  children,
}: {
  application: ApplicationDetail
  onOpenProfile: () => void
  children: ReactNode
}) {
  const { data: profile, isLoading, error } = useProfile()

  if (isLoading) return <p className="px-6 py-5 text-sm text-stone-500">Loading…</p>
  if (error) return <p className="px-6 py-5 text-sm text-rose-600">{error.message}</p>

  const hasJobDescription = Boolean(application.job_description?.trim())
  if (profile?.has_resume && hasJobDescription) return <>{children}</>

  return (
    <div className="px-6 py-5 text-sm text-stone-600">
      <p className="font-medium text-stone-800">Two things are needed first</p>
      <ul className="mt-2 space-y-1.5">
        <li>
          {profile?.has_resume ? '✓' : '○'} Your resume.{' '}
          {!profile?.has_resume && (
            <button onClick={onOpenProfile} className="text-sky-700 hover:underline">
              Upload it in Profile
            </button>
          )}
        </li>
        <li>
          {hasJobDescription ? '✓' : '○'} The job description.{' '}
          {!hasJobDescription && 'Paste it in the Details tab and save.'}
        </li>
      </ul>
    </div>
  )
}
