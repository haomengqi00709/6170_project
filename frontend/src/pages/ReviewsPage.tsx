import { useEffect, useState } from 'react'
import type { Review } from '../types'

const TIER_COLOR: Record<number, string> = {
  1: 'text-green-400 border-green-700',
  2: 'text-yellow-400 border-yellow-700',
  3: 'text-red-400 border-red-700',
}

const TIER_LABEL: Record<number, string> = {
  1: 'Tier 1 — Auto',
  2: 'Tier 2 — Queued',
  3: 'Tier 3 — Blocked',
}

export default function ReviewsPage() {
  const [reviews, setReviews]       = useState<Review[]>([])
  const [showAll, setShowAll]       = useState(false)
  const [loading, setLoading]       = useState(true)
  const [resolving, setResolving]   = useState<number | null>(null)
  const [noteMap, setNoteMap]       = useState<Record<number, string>>({})

  const load = async () => {
    setLoading(true)
    const res = await fetch(`/api/reviews?pending_only=${!showAll}`)
    const data = await res.json()
    setReviews(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [showAll])

  const resolve = async (id: number, decision: 'approved' | 'rejected') => {
    setResolving(id)
    await fetch(`/api/reviews/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, note: noteMap[id] ?? '' }),
    })
    setResolving(null)
    load()
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-lg font-bold text-yellow-400">HITL Reviews</h1>
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={showAll}
            onChange={e => setShowAll(e.target.checked)}
            className="accent-yellow-500"
          />
          Show all (including resolved)
        </label>
        <button
          onClick={load}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300 border border-gray-700 rounded px-2 py-1"
        >
          Refresh
        </button>
      </div>

      {loading && <div className="text-gray-500 text-sm">Loading…</div>}

      {!loading && reviews.length === 0 && (
        <div className="text-green-400 text-sm bg-green-950 border border-green-800 rounded p-4">
          ✅ No pending reviews — all clear.
        </div>
      )}

      <div className="space-y-4">
        {reviews.map(r => {
          const tierCls = TIER_COLOR[r.risk_tier] ?? 'text-gray-400 border-gray-700'
          const isPending = r.status === 'pending'

          return (
            <div key={r.id} className={`border rounded-lg bg-gray-900 overflow-hidden ${tierCls.split(' ')[1]}`}>
              {/* Header */}
              <div className={`px-4 py-2 border-b flex items-center gap-3 ${tierCls.split(' ')[1]} bg-gray-950`}>
                <span className={`text-xs font-bold ${tierCls.split(' ')[0]}`}>
                  {TIER_LABEL[r.risk_tier]}
                </span>
                <span className="text-gray-400 text-xs">Review #{r.id}</span>
                <span className="text-gray-400 text-xs">·</span>
                <span className="text-gray-300 text-xs font-mono">{r.action_type}</span>
                <span className="text-gray-600 text-xs ml-auto">{r.session_id}</span>
                <span className={`text-xs font-bold ml-2 ${
                  r.status === 'pending' ? 'text-yellow-400' :
                  r.reviewer_decision === 'approved' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {r.status === 'pending' ? 'PENDING' : r.reviewer_decision?.toUpperCase() ?? r.status.toUpperCase()}
                </span>
              </div>

              {/* Action detail */}
              <div className="px-4 pt-3 pb-2">
                <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Proposed Action</div>
                <div className="text-sm text-gray-200 bg-gray-800 rounded p-3 whitespace-pre-wrap max-h-32 overflow-y-auto">
                  {r.action_detail}
                </div>
              </div>

              {/* Reasoning chain */}
              {Array.isArray(r.reasoning_chain) && r.reasoning_chain.length > 0 && (
                <div className="px-4 pb-2">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Reasoning Chain</div>
                  <div className="space-y-1">
                    {(r.reasoning_chain as Record<string, unknown>[]).map((step, idx) => (
                      <div key={idx} className="flex gap-3 text-xs text-gray-400 bg-gray-800 rounded px-3 py-1.5">
                        <span className="text-gray-500 shrink-0">{String(step.action_type ?? step.action ?? idx)}</span>
                        {typeof step.anomaly_score === 'number' && (
                          <span className={step.anomaly_score < 0.65 ? 'text-red-400' : 'text-gray-400'}>
                            drift={Number(step.anomaly_score).toFixed(3)}
                          </span>
                        )}
                        {step.output_snapshot != null && (
                          <span className="truncate text-gray-500">
                            {String(step.output_snapshot).slice(0, 80)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Timestamps */}
              <div className="px-4 pb-2 flex gap-4 text-xs text-gray-600">
                <span>Created: {r.created_at.replace('T', ' ').slice(0, 19)}</span>
                {r.reviewed_at && <span>Reviewed: {r.reviewed_at.replace('T', ' ').slice(0, 19)}</span>}
                {r.reviewer_note && <span>Note: {r.reviewer_note}</span>}
              </div>

              {/* Actions */}
              {isPending && (
                <div className="border-t border-gray-800 px-4 py-3 flex gap-3 items-center bg-gray-950">
                  <input
                    type="text"
                    placeholder="Note (optional)"
                    value={noteMap[r.id] ?? ''}
                    onChange={e => setNoteMap(m => ({ ...m, [r.id]: e.target.value }))}
                    className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1 text-xs text-gray-300 focus:outline-none focus:border-gray-500"
                  />
                  <button
                    onClick={() => resolve(r.id, 'approved')}
                    disabled={resolving === r.id}
                    className="bg-green-800 hover:bg-green-700 disabled:opacity-40 text-green-100 text-xs px-4 py-1.5 rounded transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => resolve(r.id, 'rejected')}
                    disabled={resolving === r.id}
                    className="bg-red-900 hover:bg-red-800 disabled:opacity-40 text-red-100 text-xs px-4 py-1.5 rounded transition-colors"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
