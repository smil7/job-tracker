import type { JobType, Status } from '../api/types'

export const OPEN_STATUSES: Status[] = ['wishlist', 'applied', 'assessment', 'interview', 'offer']
export const CLOSED_STATUSES: Status[] = ['rejected', 'withdrawn']
export const STATUSES: Status[] = [...OPEN_STATUSES, ...CLOSED_STATUSES]

export const STATUS_META: Record<Status, { label: string; dot: string; pill: string }> = {
  wishlist: { label: 'Wishlist', dot: 'bg-stone-400', pill: 'bg-stone-200 text-stone-700' },
  applied: { label: 'Applied', dot: 'bg-sky-500', pill: 'bg-sky-100 text-sky-800' },
  assessment: { label: 'Assessment', dot: 'bg-violet-500', pill: 'bg-violet-100 text-violet-800' },
  interview: { label: 'Interview', dot: 'bg-amber-500', pill: 'bg-amber-100 text-amber-800' },
  offer: { label: 'Offer', dot: 'bg-emerald-500', pill: 'bg-emerald-100 text-emerald-800' },
  rejected: { label: 'Rejected', dot: 'bg-rose-400', pill: 'bg-rose-100 text-rose-800' },
  withdrawn: { label: 'Withdrawn', dot: 'bg-stone-300', pill: 'bg-stone-100 text-stone-500' },
}

export const JOB_TYPES: JobType[] = ['graduate_program', 'junior', 'internship', 'other']

export const JOB_TYPE_LABEL: Record<JobType, string> = {
  graduate_program: 'Graduate program',
  junior: 'Junior',
  internship: 'Internship',
  other: 'Other',
}
