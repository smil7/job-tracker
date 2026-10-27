import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Status } from '../api/types'
import { useCreateApplication } from '../hooks/useApplications'
import { emptyForm, toBody } from '../lib/form'
import { STATUS_META, STATUSES } from '../lib/status'
import { Field, FormFields, inputClass } from './FormFields'

export function QuickAddModal({ onClose }: { onClose: () => void }) {
  const create = useCreateApplication()
  const [form, setForm] = useState(emptyForm)
  const [status, setStatus] = useState<Status>('applied')
  const [more, setMore] = useState(false)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      { ...toBody(form), status, applied_at: status === 'wishlist' ? null : form.applied_at || null },
      { onSuccess: onClose },
    )
  }

  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-stone-900/30 p-4 pt-[10vh]" onMouseDown={onClose}>
      <form
        onSubmit={submit}
        onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl"
      >
        <h2 className="mb-4 text-lg font-semibold">Add application</h2>
        <FormFields form={form} onChange={setForm} essentialsOnly={!more} autoFocus />
        <Field label="Stage" className="mt-3">
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as Status)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_META[s].label}
              </option>
            ))}
          </select>
        </Field>
        {create.error && <p className="mt-3 text-sm text-rose-600">{create.error.message}</p>}
        <div className="mt-5 flex items-center gap-2">
          {!more && (
            <button type="button" onClick={() => setMore(true)} className="text-sm text-stone-500 hover:text-stone-800">
              More details
            </button>
          )}
          <button type="button" onClick={onClose} className="ml-auto rounded-md px-3 py-1.5 text-sm hover:bg-stone-100">
            Cancel
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </form>
    </div>
  )
}
