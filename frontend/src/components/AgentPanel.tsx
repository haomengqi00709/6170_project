import type { AuditEvent } from '../types'

const AGENTS = [
  { id: 'planner',     label: '1. PLANNER',     color: 'cyan' },
  { id: 'retriever',   label: '2. RETRIEVER',   color: 'blue' },
  { id: 'synthesizer', label: '3. SYNTHESIZER', color: 'green' },
] as const

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

const COLOR_CLASS: Record<string, string> = {
  cyan:  'border-cyan-600 text-cyan-400',
  blue:  'border-blue-600 text-blue-400',
  green: 'border-green-600 text-green-400',
}

const TITLE_CLASS: Record<string, string> = {
  cyan:  'text-cyan-400',
  blue:  'text-blue-400',
  green: 'text-green-400',
}

function agentStatus(events: AuditEvent[], agentId: string): { icon: string; cls: string } {
  const mine = events.filter(e => e.agent === agentId)
  if (!mine.length) return { icon: '○', cls: 'text-gray-500' }

  const hasAnomaly = events.some(
    e => e.agent === 'auditbot' && e.type === 'anomaly' &&
         (e.data as Record<string,string>).agent_step === agentId
  )
  if (hasAnomaly) return { icon: '✗', cls: 'text-red-400 font-bold' }

  const done = mine.some(e => e.type === 'done')
  if (done) return { icon: '✓', cls: 'text-green-400 font-bold' }

  return { icon: '●', cls: 'text-yellow-400 animate-pulse' }
}

interface Props {
  events: AuditEvent[]
  running: boolean
}

export default function AgentPanel({ events, running }: Props) {
  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1">
        Agent Workflow
      </div>

      {AGENTS.map((agent, i) => {
        const mine = events.filter(e => e.agent === agent.id).slice(-6)
        const { icon, cls } = agentStatus(events, agent.id)
        const colorCls = COLOR_CLASS[agent.color]
        const titleCls = TITLE_CLASS[agent.color]

        return (
          <div key={agent.id} className="flex flex-col gap-1">
            <div className={`border rounded p-3 bg-gray-900 ${colorCls} min-h-[90px]`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={cls}>{icon}</span>
                <span className={`text-xs font-bold ${titleCls}`}>{agent.label}</span>
                {running && mine.length > 0 && !mine.some(e => e.type === 'done') && (
                  <span className="ml-auto text-xs text-gray-500 animate-pulse">running…</span>
                )}
              </div>
              <div className="space-y-0.5">
                {mine.length === 0 ? (
                  <div className="text-gray-600 text-xs">Waiting…</div>
                ) : (
                  mine.map((e, idx) => (
                    <div key={idx} className={`text-xs flex gap-1 ${e.type === 'done' ? 'text-gray-500' : 'text-gray-300'}`}>
                      <span className="shrink-0">{EVENT_ICON[e.type] ?? '•'}</span>
                      <span className="truncate">{e.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {i < AGENTS.length - 1 && (
              <div className="text-center text-gray-600 text-xs">↓</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
