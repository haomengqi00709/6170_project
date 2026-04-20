import type { AuditEvent, PipelineResult } from '../types'

const EVENT_ICON: Record<string, string> = {
  thinking:    '💭',
  retrieving:  '🔍',
  found:       '📄',
  reasoning:   '🧠',
  audit:       '✅',
  anomaly:     '🔴',
  hitl:        '🚨',
  shadow_fail: '⚠️',
  done:        '✓',
  complete:    '🏁',
  error:       '❌',
}

const AGENT_COLOR: Record<string, string> = {
  planner:     'text-cyan-400',
  retriever:   'text-blue-400',
  synthesizer: 'text-green-400',
  auditbot:    'text-yellow-400',
}

function ScoreBar({ score }: { score: number }) {
  const filled = Math.round(score * 14)
  const empty  = 14 - filled
  const color  = score >= 0.80 ? 'text-green-400' : score >= 0.65 ? 'text-yellow-400' : 'text-red-400'
  return (
    <span className={`font-mono text-xs ${color}`}>
      {'█'.repeat(filled)}{'░'.repeat(empty)}
      <span className="text-gray-400 ml-1">{score.toFixed(3)}</span>
    </span>
  )
}

interface Props {
  events: AuditEvent[]
  result: PipelineResult | null
  running: boolean
}

export default function AuditPanel({ events, result, running }: Props) {
  // Drift scores from audit events
  const auditEvts = events.filter(
    e => e.agent === 'auditbot' && ['audit', 'anomaly'].includes(e.type) && 'score' in e.data
  )
  const scores: Record<string, number> = {}
  for (const e of auditEvts) {
    const step = (e.data.agent_step as string) ?? '?'
    scores[step] = e.data.score as number
  }

  // Status
  const anomalies   = events.filter(e => e.type === 'anomaly')
  const hitlEvents  = events.filter(e => e.type === 'hitl')
  const completeEvt = events.filter(e => e.type === 'complete')

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">
        AuditBot Monitor
      </div>

      {/* Audit log */}
      <div className="border border-yellow-700 rounded bg-gray-900 flex-1 overflow-hidden flex flex-col">
        <div className="text-xs font-bold text-yellow-400 px-3 py-1.5 border-b border-yellow-900">
          Audit Log
        </div>
        <div className="overflow-y-auto flex-1 px-2 py-1">
          {events.length === 0 ? (
            <div className="text-gray-600 text-xs p-2">Waiting for events…</div>
          ) : (
            events.slice(-20).map((e, idx) => {
              const isBad = ['anomaly', 'hitl', 'shadow_fail', 'error'].includes(e.type)
              return (
                <div key={idx} className={`flex gap-2 text-xs py-0.5 ${isBad ? 'text-red-400 font-semibold' : 'text-gray-300'}`}>
                  <span className="text-gray-600 shrink-0 w-16">{e.ts}</span>
                  <span className={`shrink-0 w-20 ${AGENT_COLOR[e.agent] ?? 'text-gray-400'}`}>{e.agent}</span>
                  <span className="truncate">{EVENT_ICON[e.type] ?? '•'} {e.message}</span>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Drift scores */}
      <div className="border border-yellow-700 rounded bg-gray-900 p-3">
        <div className="text-xs font-bold text-yellow-400 mb-2">Drift Scores</div>
        {Object.keys(scores).length === 0 ? (
          <div className="text-gray-600 text-xs">Waiting for data…</div>
        ) : (
          <div className="space-y-1">
            {Object.entries(scores).map(([step, score]) => (
              <div key={step} className="flex items-center gap-3 text-xs">
                <span className="text-gray-400 w-20 shrink-0">{step}</span>
                <ScoreBar score={score} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Status */}
      <div className="border border-yellow-700 rounded bg-gray-900 p-3">
        <div className="text-xs font-bold text-yellow-400 mb-2">Status</div>
        {running && !result && anomalies.length === 0 && hitlEvents.length === 0 && completeEvt.length === 0 && (
          <div className="text-yellow-300 text-xs animate-pulse">⏳ Running…</div>
        )}
        {anomalies.length > 0 && (
          <div>
            <div className="text-red-400 font-bold text-sm">⚠ SUSPENDED</div>
            <div className="text-red-300 text-xs mt-1">{anomalies[anomalies.length - 1].message}</div>
          </div>
        )}
        {hitlEvents.length > 0 && (
          <div>
            {(() => {
              const last = hitlEvents[hitlEvents.length - 1]
              const tier = last.data.tier as number
              const rid  = last.data.review_id
              return (
                <div>
                  <div className={`font-bold text-sm ${tier === 3 ? 'text-red-400' : 'text-yellow-400'}`}>
                    {tier === 3 ? '🔴 BLOCKED' : '🟡 QUEUED'} — Tier {tier}
                  </div>
                  <div className="text-gray-400 text-xs mt-1">Action: {result?.action_type ?? '?'}</div>
                  <div className="text-gray-400 text-xs">Review ID: {String(rid)}</div>
                  <div className="text-gray-600 text-xs mt-1">→ Go to HITL Reviews tab</div>
                </div>
              )
            })()}
          </div>
        )}
        {completeEvt.length > 0 && anomalies.length === 0 && hitlEvents.length === 0 && (
          <div>
            <div className="text-green-400 font-bold text-sm">🏁 COMPLETE</div>
            {result && <div className="text-green-300 text-xs mt-1">Action: {result.action_type}</div>}
          </div>
        )}
      </div>
    </div>
  )
}
