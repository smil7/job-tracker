import type { ReactNode } from 'react'
import type { JobType } from '../api/types'
import type { FormState } from '../lib/form'
import { JOB_TYPE_LABEL, JOB_TYPES } from '../lib/status'

export const inputClass =
  'w-full rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-stone-500 focus:ring-2 focus:ring-stone-200'

export function Field({ label, children, className = '' }: { label: string; children: ReactNode; className?: string }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      <span className="text-xs font-medium text-stone-500">{label}</span>
      {children}
    </label>
  )
}

type Props = {
  form: FormState
  onChange: (form: FormState) => void
  /** Hide the less common fields (used by quick add until "More details" is clicked). */
  essentialsOnly?: boolean
  autoFocus?: boolean
}

export function FormFields({ form, onChange, essentialsOnly = false, autoFocus = false }: Props) {
  const set = (key: keyof FormState) => (e: { target: { value: string } }) => onChange({ ...form, [key]: e.target.value })

  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Company *">
        <input className={inputClass} value={form.company} onChange={set('company')} autoFocus={autoFocus} required />
      </Field>
      <Field label="Role *">
        <input className={inputClass} value={form.role} onChange={set('role')} required />
      </Field>
      <Field label="Type">
        <select className={inputClass} value={form.job_type} onChange={set('job_type')}>
          <option value="">—</option>
          {JOB_TYPES.map((t: JobType) => (
            <option key={t} value={t}>
              {JOB_TYPE_LABEL[t]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Location">
        <input className={inputClass} value={form.location} onChange={set('location')} placeholder="Dubai, Remote…" />
      </Field>
      <Field label="Job link" className="col-span-2">
        <input className={inputClass} value={form.job_url} onChange={set('job_url')} placeholder="https://" type="url" />
      </Field>
      {!essentialsOnly && (
        <>
          <Field label="Applied on">
            <input className={inputClass} type="date" value={form.applied_at} onChange={set('applied_at')} />
          </Field>
          <Field label="Deadline">
            <input className={inputClass} type="date" value={form.deadline} onChange={set('deadline')} />
          </Field>
          <Field label="Source">
            <input className={inputClass} value={form.source} onChange={set('source')} placeholder="LinkedIn, referral…" />
          </Field>
          <Field label="Salary">
            <input className={inputClass} value={form.salary} onChange={set('salary')} />
          </Field>
          <Field label="Notes" className="col-span-2">
            <textarea className={`${inputClass} min-h-20`} value={form.notes} onChange={set('notes')} />
          </Field>
          <Field label="Job description" className="col-span-2">
            <textarea
              className={`${inputClass} min-h-28`}
              value={form.job_description}
              onChange={set('job_description')}
              placeholder="Paste the posting so you have it after it's taken down"
            />
          </Field>
        </>
      )}
    </div>
  )
}
