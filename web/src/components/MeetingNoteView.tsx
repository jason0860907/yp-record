import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Loader2 } from 'lucide-react'
import { marked } from 'marked'
import { getMeetingNote } from '../api/client'

marked.setOptions({ breaks: true, gfm: true })

interface Props {
  sessionId: string
}

export default function MeetingNoteView({ sessionId }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['meeting-note', sessionId],
    queryFn: () => getMeetingNote(sessionId),
    retry: false,
  })

  const html = useMemo(() => {
    if (!data?.content) return ''
    return marked.parse(data.content) as string
  }, [data?.content])

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading meeting note...
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <FileText className="h-8 w-8 text-slate-300" />
        <p className="text-sm text-slate-400">
          No meeting note yet. Click "Extract" to generate one.
        </p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <article className="prose prose-slate prose-sm max-w-none">
        <div dangerouslySetInnerHTML={{ __html: html }} />
      </article>
      <div className="mt-6 flex items-center gap-3 text-xs text-slate-400">
        {data.tags.map((tag) => (
          <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5">{tag}</span>
        ))}
        <span>{new Date(data.created_at).toLocaleString()}</span>
      </div>
    </div>
  )
}
