import { differenceInCalendarDays, format, formatDistanceToNowStrict, parseISO } from 'date-fns'

export const todayISO = () => format(new Date(), 'yyyy-MM-dd')

export const formatDay = (iso: string | null | undefined) =>
  iso ? format(parseISO(iso), 'd MMM yyyy') : '—'

export const ago = (iso: string) => formatDistanceToNowStrict(parseISO(iso), { addSuffix: true })

/** Relative wording for a date-only value (no time of day), e.g. an applied date. */
export function daysAgo(iso: string) {
  const days = differenceInCalendarDays(new Date(), parseISO(iso))
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return days > 1 && days < 30 ? `${days} days ago` : formatDay(iso)
}

/** Days until a deadline (negative when past), or null when there is none. */
export const daysUntil = (iso: string | null | undefined) =>
  iso ? differenceInCalendarDays(parseISO(iso), new Date()) : null
