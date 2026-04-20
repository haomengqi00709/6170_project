import { useEffect, useState } from 'react'
import type { Session } from '../types'

const STATUS_COLOR: Record<string, string> = {
  active:     'text-yellow-400',
  completed:  'text-green-400',
  suspended:  'text-red-400',
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading]   = useState(true)

  const load = async () => {
    setLoading(true)
    const res = await fetch('/api/sessions')
    const data = await res.json()
    setSessions(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-lg font-bold text-purple-400">Sessions</h1>
        <button
          onClick={load}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300 border border-gray-700 rounded px-2 py-1"
        >
          Refresh
        </button>
      </div>

      {loading && <div className="text-gray-500 text-sm">Loading…</div>}

      {!loading && sessions.length === 0 && (
        <div className="text-gray-500 text-sm">No sessions yet. Run a demo query first.</div>
      )}

      <div className="border border-gray-800 rounded-lg overflow-hidden">
        {sessions.map((s, idx) => (
          <div
            key={s.session_id}
            className={`px-4 py-3 flex gap-4 items-start text-sm ${idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-950'} border-b border-gray-800 last:border-b-0`}
          >
            <span className="font-mono text-cyan-500 shrink-0 text-xs mt-0.5">{s.session_id}</span>
            <span className={`shrink-0 text-xs font-bold mt-0.5 w-20 ${STATUS_COLOR[s.status] ?? 'text-gray-400'}`}>
              {s.status.toUpperCase()}
            </span>
            <span className="text-gray-400 text-xs shrink-0 mt-0.5 w-16">{s.user_id}</span>
            <span className="text-gray-200 flex-1 text-xs leading-relaxed">{s.question}</span>
            <span className="text-gray-600 text-xs shrink-0 mt-0.5">
              {s.started_at.replace('T', ' ').slice(0, 19)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
