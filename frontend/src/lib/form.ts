import type { Application, JobType } from '../api/types'
import { todayISO } from './dates'

/** Editable fields as plain strings; empty strings become null when sent to the API. */
export type FormState = {
  company: string
  role: string
  job_type: JobType | ''
  location: string
  job_url: string
  source: string
  applied_at: string
  deadline: string
  salary: string
  notes: string
  job_description: string
}

export const emptyForm = (): FormState => ({
  company: '',
  role: '',
  job_type: '',
  location: '',
  job_url: '',
  source: '',
  applied_at: todayISO(),
  deadline: '',
  salary: '',
  notes: '',
  job_description: '',
})

export const fromApplication = (a: Application): FormState => ({
  company: a.company,
  role: a.role,
  job_type: a.job_type ?? '',
  location: a.location ?? '',
  job_url: a.job_url ?? '',
  source: a.source ?? '',
  applied_at: a.applied_at ?? '',
  deadline: a.deadline ?? '',
  salary: a.salary ?? '',
  notes: a.notes ?? '',
  job_description: a.job_description ?? '',
})

const orNull = (value: string) => value.trim() || null

export const toBody = (f: FormState) => ({
  company: f.company.trim(),
  role: f.role.trim(),
  job_type: f.job_type || null,
  location: orNull(f.location),
  job_url: orNull(f.job_url),
  source: orNull(f.source),
  applied_at: f.applied_at || null,
  deadline: f.deadline || null,
  salary: orNull(f.salary),
  notes: orNull(f.notes),
  job_description: orNull(f.job_description),
})
