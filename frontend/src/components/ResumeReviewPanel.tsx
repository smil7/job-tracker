import { format, parseISO } from 'date-fns'
import type { ATSReview } from '../api/types'
import { useResumeReview, useRunReview } from '../hooks/useApplications'

const scoreColour = (score: number) =>
  score >= 75 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-rose-600'

const barColour = (score: number) => (score >= 75 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-rose-500')

export function ResumeReviewPanel({ applicationId }: { applicationId: string }) {
  const { data: stored, isLoading, error } = useResumeReview(applicationId)
  const run = useRunReview(applicationId)

  return (
    <section className="px-6 py-5">
      <div className="mb-4 flex items-center gap-3">
        <h3 className="text-sm font-semibold">Resume review</h3>
        {stored && (
          <time className="text-xs text-stone-500">
            Last run {format(parseISO(stored.created_at), 'd MMM yyyy, HH:mm')}
          </time>
        )}
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="ml-auto rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50"
        >
          {run.isPending ? 'Reviewing…' : stored ? 'Re-run' : 'Review my resume'}
        </button>
      </div>

      {run.isPending && (
        <p className="mb-4 text-sm text-stone-500">Reading your resume against the job description. This takes up to a minute.</p>
      )}
      {run.error && <p className="mb-4 text-sm text-rose-600">{run.error.message}</p>}
      {isLoading && <p className="text-sm text-stone-500">Loading…</p>}
      {error && <p className="text-sm text-rose-600">{error.message}</p>}
      {stored === null && !run.isPending && (
        <p className="text-sm text-stone-500">
          Scores your resume against this job the way an ATS would, and suggests concrete edits.
        </p>
      )}
      {stored && <ReviewBody review={stored.review} />}
    </section>
  )
}

function ReviewBody({ review }: { review: ATSReview }) {
  const sections = Object.entries(review.section_scores)
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <ScoreRing score={review.overall_score} />
        <p className="text-sm text-stone-700">{review.summary}</p>
      </div>

      <div className="space-y-2">
        {sections.map(([name, score]) => (
          <div key={name} className="flex items-center gap-3 text-sm">
            <span className="w-24 capitalize text-stone-600">{name}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-stone-100">
              <div className={`h-full ${barColour(score)}`} style={{ width: `${score}%` }} />
            </div>
            <span className="w-8 text-right tabular-nums text-stone-500">{score}</span>
          </div>
        ))}
      </div>

      <div>
        <h4 className="mb-2 text-xs font-medium text-stone-500">Keywords</h4>
        <div className="flex flex-wrap gap-1.5">
          {review.keywords.matched.map((k) => (
            <span key={`m-${k}`} className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">
              {k}
            </span>
          ))}
          {review.keywords.missing.map((k) => (
            <span key={`x-${k}`} className="rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-800">
              {k}
            </span>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-stone-400">Green: found in your resume. Red: missing.</p>
      </div>

      <ListBlock title="Formatting issues" items={review.formatting_issues} />
      <ListBlock title="Strengths" items={review.strengths} />
      <ListBlock title="Gaps" items={review.gaps} />

      {review.suggested_edits.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium text-stone-500">Suggested edits</h4>
          <ul className="space-y-3">
            {review.suggested_edits.map((edit, i) => (
              <li key={i} className="rounded-lg border border-stone-200 p-3 text-sm">
                <p className="text-xs font-medium text-stone-500">{edit.section}</p>
                <p className="mt-1 text-stone-500 line-through decoration-stone-300">{edit.current}</p>
                <p className="mt-1 text-stone-900">{edit.suggestion}</p>
                <p className="mt-1.5 text-xs text-stone-500">{edit.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium text-stone-500">{title}</h4>
      <ul className="list-disc space-y-1 pl-5 text-sm text-stone-700">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  const radius = 26
  const circumference = 2 * Math.PI * radius
  return (
    <div className={`relative size-16 shrink-0 ${scoreColour(score)}`} role="img" aria-label={`Score ${score} out of 100`}>
      <svg viewBox="0 0 64 64" className="size-full -rotate-90">
        <circle cx="32" cy="32" r={radius} fill="none" strokeWidth="6" className="stroke-stone-100" />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          stroke="currentColor"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-lg font-semibold tabular-nums">{score}</span>
    </div>
  )
}
