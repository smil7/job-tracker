import { useStats } from '../hooks/useApplications'

export function StatsStrip() {
  const { data } = useStats()
  const items = [
    { label: 'Applied', value: data?.total_applied },
    { label: 'This week', value: data?.applied_this_week },
    { label: 'Active', value: data?.active },
    { label: 'Interviews', value: data?.interviews },
    { label: 'Offers', value: data?.offers },
    { label: 'Response rate', value: data ? `${Math.round(data.response_rate * 100)}%` : undefined },
  ]
  return (
    <dl className="flex flex-wrap gap-x-8 gap-y-2">
      {items.map((item) => (
        <div key={item.label}>
          <dt className="text-xs text-stone-500">{item.label}</dt>
          <dd className="text-xl font-semibold tabular-nums">{item.value ?? '–'}</dd>
        </div>
      ))}
    </dl>
  )
}
