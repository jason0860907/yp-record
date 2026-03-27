import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import SessionSidebar from './SessionSidebar'
import MainPane from './MainPane'

export default function RecordPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen overflow-hidden p-3 gap-3">
      {/* Sidebar */}
      <div
        className={`flex-shrink-0 transition-all duration-300 ease-in-out ${
          sidebarOpen ? 'w-72' : 'w-0'
        } overflow-hidden`}
      >
        <div className="h-full rounded-2xl glass-sidebar overflow-hidden">
          <SessionSidebar />
        </div>
      </div>

      {/* Toggle button */}
      <div className="relative flex-shrink-0 flex items-start pt-4">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="flex h-7 w-7 items-center justify-center rounded-full glass text-slate-500 hover:text-slate-700 transition-colors duration-200 cursor-pointer"
          aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {/* Main pane */}
      <div className="flex-1 overflow-hidden rounded-2xl glass">
        <MainPane />
      </div>
    </div>
  )
}
