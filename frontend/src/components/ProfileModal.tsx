import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import type { Profile } from '../api/types'
import { useProfile, useUpdateProfile, useUploadResume } from '../hooks/useApplications'
import { Field, inputClass } from './FormFields'

export function ProfileModal({ onClose }: { onClose: () => void }) {
  const { data: profile, isLoading, error } = useProfile()

  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-stone-900/30 p-4 pt-[10vh]" onMouseDown={onClose}>
      <div onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl">
        <h2 className="mb-1 text-lg font-semibold">Profile</h2>
        <p className="mb-4 text-sm text-stone-500">Used by the resume review and cover letter tools.</p>
        {isLoading && <p className="text-sm text-stone-500">Loading…</p>}
        {error && <p className="text-sm text-rose-600">{error.message}</p>}
        {profile && <ProfileForm profile={profile} onClose={onClose} />}
      </div>
    </div>
  )
}

function ProfileForm({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  const update = useUpdateProfile()
  const upload = useUploadResume()
  const fileRef = useRef<HTMLInputElement>(null)
  const [aboutMe, setAboutMe] = useState(profile.about_me ?? '')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    update.mutate(aboutMe.trim() || null, { onSuccess: onClose })
  }

  return (
    <form onSubmit={submit}>
      <Field label="Resume (PDF, up to 5 MB)">
        <div className="flex items-center gap-3">
          <span className="min-w-0 flex-1 truncate text-sm text-stone-700">
            {upload.isPending ? 'Uploading…' : (profile.resume_filename ?? 'No resume uploaded')}
          </span>
          {profile.has_resume && (
            <a href="/api/profile/resume" target="_blank" rel="noreferrer" className="text-sm text-sky-700 hover:underline">
              View
            </a>
          )}
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            className="rounded-md border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100 disabled:opacity-50"
          >
            {profile.has_resume ? 'Replace' : 'Upload'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) upload.mutate(file)
              e.target.value = ''
            }}
          />
        </div>
      </Field>
      {upload.error && <p className="mt-2 text-sm text-rose-600">{upload.error.message}</p>}

      <Field label="About me" className="mt-4">
        <textarea
          className={`${inputClass} min-h-40`}
          value={aboutMe}
          onChange={(e) => setAboutMe(e.target.value)}
          placeholder="Anything not on your resume that a cover letter could use: what you're looking for, projects you're proud of, your name and contact details…"
        />
      </Field>
      {update.error && <p className="mt-3 text-sm text-rose-600">{update.error.message}</p>}

      <div className="mt-5 flex items-center gap-2">
        <button type="button" onClick={onClose} className="ml-auto rounded-md px-3 py-1.5 text-sm hover:bg-stone-100">
          Cancel
        </button>
        <button
          type="submit"
          disabled={update.isPending}
          className="rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </form>
  )
}
