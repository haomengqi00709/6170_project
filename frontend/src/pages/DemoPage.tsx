import { useState, useEffect, useRef } from 'react'
import { usePipeline } from '../hooks/usePipeline'
import AgentPanel from '../components/AgentPanel'
import AuditPanel from '../components/AuditPanel'
import type { AuditEvent, PipelineResult } from '../types'

type Mode = 'audited' | 'baseline'

const AGENT_COLOR: Record<string, string> = {
  planner: 'text-cyan-400', retriever: 'text-blue-400',
  synthesizer: 'text-green-400', auditbot: 'text-yellow-400',
}
const EVENT_ICON: Record<string, string> = {
  thinking: '💭', retrieving: '🔍', found: '📄', reasoning: '🧠',
  email: '📧', done: '✓', complete: '🏁', error: '❌', blocked: '🔒',
}

export default function DemoPage() {
  const [mode, setMode]           = useState<Mode>('baseline')
  const [chunkCount, setChunkCount] = useState<number | null>(null)
  const [fixedTask, setFixedTask]   = useState('')
  const [seeding, setSeeding]       = useState<string | null>(null)
  const [seedMsg, setSeedMsg]       = useState<string | null>(null)
  const [step, setStep]             = useState<1 | 2 | 3>(1)

  const { events, result, running, error, sessionId, run, reset } = usePipeline()
  const logBottomRef = useRef<HTMLDivElement>(null)

  const fetchStatus = () =>
    fetch('/api/demo/status').then(r => r.json())
      .then(d => { setChunkCount(d.chunk_count); setFixedTask(d.fixed_task || '') })
      .catch(() => {})

  useEffect(() => { fetchStatus() }, [])

  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  const handleSeed = async (endpoint: 'seed-clean' | 'seed-poison') => {
    setSeeding(endpoint)
    setSeedMsg(null)
    reset()
    try {
      const res  = await fetch(`/api/demo/${endpoint}`, { method: 'POST' })
      const data = await res.json()
      if (data.ok) {
        const names = data.files.map((f: { file: string }) => f.file).join(', ')
        setSeedMsg(`${data.total_chunks} chunks — ${names}`)
        setChunkCount(data.total_chunks)
        if (endpoint === 'seed-clean') setStep(1)
        if (endpoint === 'seed-poison') setStep(2)
      } else {
        setSeedMsg(data.detail ?? 'Seed failed')
      }
    } catch (e) { setSeedMsg(String(e)) }
    finally { setSeeding(null) }
  }

  const handleRun = () => {
    if (running) return
    // use /api/demo/run (fixed task endpoint) via the SSE pipeline
    run('__demo__', 'bob', mode)
  }

  const isBaseline = mode === 'baseline'

  return (
    <div className="flex flex-col h-[calc(100vh-53px)]">

      {/* ── 3-Step guide ────────────────────────────────────────────────────── */}
      <div className="border-b border-gray-800 bg-gray-950 px-5 py-3 shrink-0 flex items-start gap-8 flex-wrap text-xs">

        {/* Step 1 */}
        <div className="flex items-start gap-3">
          <StepBadge n={1} active={step >= 1} done={step > 1} />
          <div>
            <div className="text-gray-200 font-semibold mb-0.5">Clean Workflow</div>
            <div className="text-gray-500 mb-1.5">
              personal_profile.txt (senior)<br />
              web_article.txt (public, no injection)
            </div>
            <button onClick={() => handleSeed('seed-clean')}
              disabled={!!seeding || running}
              className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 px-3 py-1 rounded text-xs transition-colors">
              {seeding === 'seed-clean' ? 'Seeding…' : '⟳ Seed Clean'}
            </button>
          </div>
        </div>

        <div className="text-gray-700 text-lg mt-3">→</div>

        {/* Step 2 */}
        <div className="flex items-start gap-3">
          <StepBadge n={2} active={step >= 2} done={step > 2} />
          <div>
            <div className="text-gray-200 font-semibold mb-0.5">Add Poison</div>
            <div className="text-gray-500 mb-1.5">
              Manually add injection text to<br />
              <code className="text-orange-400">data/raw/public/web_article.txt</code>
            </div>
            <button onClick={() => handleSeed('seed-poison')}
              disabled={!!seeding || running}
              className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 px-3 py-1 rounded text-xs transition-colors">
              {seeding === 'seed-poison' ? 'Re-seeding…' : '⟳ Re-seed After Poison'}
            </button>
          </div>
        </div>

        <div className="text-gray-700 text-lg mt-3">→</div>

        {/* Step 3 */}
        <div className="flex items-start gap-3">
          <StepBadge n={3} active={step >= 3} done={false} />
          <div>
            <div className="text-gray-200 font-semibold mb-0.5">Enable AuditBot</div>
            <div className="text-gray-500 mb-1.5">
              Toggle to "With AuditBot"<br />
              Extra email gets blocked
            </div>
            <button onClick={() => { reset(); setMode('audited'); setStep(3) }}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                !isBaseline
                  ? 'bg-cyan-800 text-cyan-200'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              }`}>
              {!isBaseline ? '✓ AuditBot ON' : 'Turn On AuditBot'}
            </button>
          </div>
        </div>

        {/* Status */}
        <div className="ml-auto text-gray-600 text-right self-center">
          {chunkCount !== null && (
            <div className={chunkCount === 0 ? 'text-yellow-600' : 'text-green-600'}>
              {chunkCount === 0 ? '⚠ Empty — seed first' : `✓ ${chunkCount} chunks loaded`}
            </div>
          )}
          {seedMsg && <div className="text-gray-500 max-w-xs truncate">{seedMsg}</div>}
        </div>
      </div>

      {/* ── Fixed task display + Run button ─────────────────────────────────── */}
      <div className="border-b border-gray-800 bg-gray-900 px-5 py-3 shrink-0 flex items-center gap-4">
        {/* Mode toggle */}
        <div className="flex rounded overflow-hidden border border-gray-700 text-xs shrink-0">
          <button type="button" onClick={() => { reset(); setMode('baseline') }}
            className={`px-3 py-1.5 transition-colors ${
              isBaseline ? 'bg-gray-600 text-gray-100 font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}>
            Without AuditBot
          </button>
          <button type="button" onClick={() => { reset(); setMode('audited'); setStep(3) }}
            className={`px-3 py-1.5 transition-colors border-l border-gray-700 ${
              !isBaseline ? 'bg-cyan-900 text-cyan-200 font-bold' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}>
            With AuditBot
          </button>
        </div>

        {/* Fixed task */}
        <div className="flex-1 text-xs text-gray-400 bg-gray-800 rounded px-3 py-2 border border-gray-700">
          <span className="text-gray-600 mr-2">Fixed task:</span>
          {fixedTask || 'Loading…'}
        </div>

        {/* Run / New Query */}
        <button onClick={handleRun} disabled={running || chunkCount === 0}
          className="bg-cyan-700 hover:bg-cyan-600 disabled:opacity-40 text-white text-sm px-5 py-2 rounded transition-colors shrink-0">
          {running ? 'Running…' : 'Run'}
        </button>
        {(events.length > 0 || result) && (
          <button onClick={() => reset()} disabled={running}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 text-sm px-3 py-2 rounded transition-colors flex items-center gap-1.5 shrink-0">
            <span>↺</span><span>New</span>
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-950 border-b border-red-800 px-4 py-2 text-red-300 text-sm shrink-0">
          Error: {error}
        </div>
      )}

      {/* Session banner */}
      {sessionId && (
        <div className="border-b border-gray-800 bg-gray-900 px-4 py-1 text-xs shrink-0 flex items-center gap-3 text-gray-600">
          <span className={isBaseline ? 'text-gray-500' : 'text-cyan-600 font-semibold'}>
            {isBaseline ? 'Baseline' : '✓ AuditBot active'}
          </span>
          <span>Session: <span className="font-mono text-cyan-700">{sessionId}</span></span>
        </div>
      )}

      {/* ── Split panel ──────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 border-r border-gray-800 overflow-y-auto p-4">
          <AgentPanel events={events} running={running} />
        </div>
        <div className="w-1/2 overflow-y-auto p-4 flex flex-col gap-3">
          {isBaseline
            ? <BaselineLog events={events} result={result} />
            : <AuditPanel  events={events} result={result} running={running} />
          }
        </div>
      </div>

      {/* ── Result panel ─────────────────────────────────────────────────────── */}
      {result && (
        <div className="border-t border-gray-800 bg-gray-900 p-4 max-h-52 overflow-y-auto shrink-0">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-3 flex-wrap">
            <span>Result</span>
            <span className={`font-bold ${
              result.session_status === 'completed'      ? 'text-green-400' :
              result.session_status === 'pending_review' ? 'text-red-400'   :
              result.session_status === 'suspended'      ? 'text-red-400'   :
              'text-gray-400'
            }`}>
              [{result.session_status.toUpperCase()}]
            </span>
            {result.email_action && result.email_action.emails.length > 0 && (
              <span className="font-bold text-green-400">
                📧 Sent to: {result.email_action.emails.map(e => e.to).join(', ')}
              </span>
            )}
            {result.blocked_recipients && result.blocked_recipients.length > 0 && (
              <span className="font-bold text-red-400">
                🔒 Blocked: {result.blocked_recipients.join(', ')}
              </span>
            )}
            {result.cited_sources.length > 0 && (
              <span className="text-gray-600 ml-auto">
                Sources: {result.cited_sources.join(', ')}
              </span>
            )}
          </div>
          <div className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
            {result.answer || '(No answer)'}
          </div>
          <div ref={logBottomRef} />
        </div>
      )}
    </div>
  )
}


// ── Step badge ────────────────────────────────────────────────────────────────
function StepBadge({ n, active, done }: { n: number; active: boolean; done: boolean }) {
  return (
    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
      done   ? 'bg-green-700 text-white' :
      active ? 'bg-cyan-800 text-cyan-100' :
               'bg-gray-700 text-gray-400'
    }`}>
      {done ? '✓' : n}
    </div>
  )
}


// ── Baseline right panel ──────────────────────────────────────────────────────
function BaselineLog({ events, result }: { events: AuditEvent[]; result: PipelineResult | null }) {
  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">Event Log</div>

      <div className="border border-gray-700 rounded bg-gray-900 flex-1 overflow-hidden flex flex-col">
        <div className="overflow-y-auto flex-1 px-2 py-1">
          {events.length === 0
            ? <div className="text-gray-600 text-xs p-2">Waiting…</div>
            : events.map((e, idx) => (
                <div key={idx} className="flex gap-2 text-xs py-0.5 text-gray-400">
                  <span className="text-gray-600 shrink-0 w-16">{e.ts}</span>
                  <span className={`shrink-0 w-20 ${AGENT_COLOR[e.agent] ?? 'text-gray-500'}`}>{e.agent}</span>
                  <span className="truncate">{EVENT_ICON[e.type] ?? '•'} {e.message}</span>
                </div>
              ))
          }
        </div>
      </div>

      <div className="border border-gray-700 rounded bg-gray-900 p-3">
        <div className="text-xs font-bold text-gray-400 mb-2">Status</div>
        {result
          ? <div className="text-green-400 text-sm">✓ Completed — {result.action_type}</div>
          : <div className="text-gray-500 text-xs animate-pulse">Running…</div>
        }
      </div>
    </div>
  )
}
