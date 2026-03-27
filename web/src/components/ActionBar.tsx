import { useState } from 'react'
import { ExternalLink, FileText, Loader2, Sparkles, Wand2 } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { exportToNotion, triggerAlignment, triggerExtract, getConfig } from '../api/client'
import { useStore } from '../store/useStore'
import toast from 'react-hot-toast'

interface Props {
  sessionId: string
}

export default function ActionBar({ sessionId }: Props) {
  const [exporting, setExporting] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [notionUrl, setNotionUrl] = useState<string | null>(null)
  const setActiveTab = useStore((s) => s.setActiveTab)
  const queryClient = useQueryClient()

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
    staleTime: Infinity,
  })

  const handleExport = async () => {
    setExporting(true)
    try {
      const result = await exportToNotion(sessionId)
      setNotionUrl(result.url)
      toast.success('Exported to Notion')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed'
      toast.error(msg)
    } finally {
      setExporting(false)
    }
  }

  const handleProcessAlignment = async () => {
    try {
      await triggerAlignment(sessionId)
      setActiveTab('alignment')
      toast.success('Alignment started')
    } catch {
      toast.error('Failed to start alignment')
    }
  }

  const handleExtract = async () => {
    setExtracting(true)
    try {
      const result = await triggerExtract(sessionId)
      queryClient.invalidateQueries({ queryKey: ['meeting-note', sessionId] })
      setActiveTab('note')
      toast.success(result.meeting_note_title ? `Generated: ${result.meeting_note_title}` : 'Extraction completed')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Extraction failed'
      toast.error(msg)
    } finally {
      setExtracting(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleProcessAlignment}
        className="glass-btn flex items-center gap-1.5 text-slate-600 hover:text-slate-800"
      >
        <Wand2 className="h-3.5 w-3.5" />
        Process Alignment
      </button>

      {config?.extract_enabled && (
        <button
          onClick={handleExtract}
          disabled={extracting}
          className="glass-btn flex items-center gap-1.5 text-slate-600 hover:text-slate-800 disabled:opacity-50"
        >
          {extracting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          {extracting ? 'Extracting...' : 'Extract'}
        </button>
      )}

      {config?.notion_enabled && (
        <>
          {notionUrl ? (
            <a
              href={notionUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 transition-all duration-200 cursor-pointer shadow-sm"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View in Notion
            </a>
          ) : (
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-dark disabled:opacity-50 transition-all duration-200 cursor-pointer shadow-sm"
            >
              {exporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M4 2h16a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm7 3H7v14l4-4 4 4V5h-4z" />
                </svg>
              )}
              {exporting ? 'Exporting...' : 'Export to Notion'}
            </button>
          )}
        </>
      )}
    </div>
  )
}
