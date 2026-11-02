import { useState } from 'react'
import type { CoverLetter } from '../api/types'
import { useCoverLetter, useGenerateCoverLetter, useSaveCoverLetter } from '../hooks/useApplications'
import { inputClass } from './FormFields'

export function CoverLetterPanel({ applicationId }: { applicationId: string }) {
  const { data: letter, isLoading, error } = useCoverLetter(applicationId)
  const generate = useGenerateCoverLetter(applicationId)
  const [instructions, setInstructions] = useState('')

  const run = () => generate.mutate(instructions.trim() || null)

  return (
    <section className="px-6 py-5">
      <h3 className="mb-3 text-sm font-semibold">Cover letter</h3>
      <div className="flex gap-2">
        <input
          className={inputClass}
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="Optional: more formal, under 300 words…"
        />
        <button
          onClick={run}
          disabled={generate.isPending}
          className="shrink-0 rounded-md bg-stone-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-50"
        >
          {generate.isPending ? 'Writing…' : letter ? 'Regenerate' : 'Generate'}
        </button>
      </div>
      {generate.isPending && <p className="mt-3 text-sm text-stone-500">Drafting from your resume. This takes up to a minute.</p>}
      {generate.error && <p className="mt-3 text-sm text-rose-600">{generate.error.message}</p>}
      {isLoading && <p className="mt-3 text-sm text-stone-500">Loading…</p>}
      {error && <p className="mt-3 text-sm text-rose-600">{error.message}</p>}
      {letter === null && !generate.isPending && (
        <p className="mt-3 text-sm text-stone-500">
          Drafts a letter for this role using only what is in your resume and Profile. Edit it freely afterwards.
        </p>
      )}
      {/* key resets the editor when a new letter is generated */}
      {letter && <LetterEditor key={letter.generated_at} applicationId={applicationId} letter={letter} />}
    </section>
  )
}

function LetterEditor({ applicationId, letter }: { applicationId: string; letter: CoverLetter }) {
  const save = useSaveCoverLetter(applicationId)
  const [text, setText] = useState(letter.content)

  return (
    <div className="mt-4">
      <textarea
        className={`${inputClass} min-h-96 leading-relaxed`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => text !== letter.content && save.mutate(text)}
      />
      <div className="mt-2 flex items-center gap-3 text-xs text-stone-500">
        <span>
          {save.isPending ? 'Saving…' : save.error ? <span className="text-rose-600">{save.error.message}</span> : 'Saved when you click away'}
        </span>
        <a
          href={`/api/applications/${applicationId}/cover-letter.docx`}
          className="ml-auto rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-100"
        >
          Download .docx
        </a>
      </div>
    </div>
  )
}
