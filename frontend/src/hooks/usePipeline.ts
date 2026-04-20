import { useState, useRef, useCallback } from 'react'
import type { AuditEvent, PipelineResult } from '../types'

interface PipelineState {
  sessionId: string | null
  events: AuditEvent[]
  result: PipelineResult | null
  running: boolean
  error: string | null
}

export function usePipeline() {
  const [state, setState] = useState<PipelineState>({
    sessionId: null,
    events: [],
    result: null,
    running: false,
    error: null,
  })

  const esRef = useRef<EventSource | null>(null)

  const run = useCallback(async (question: string, userId: string, mode: string = 'audited') => {
    // close any previous stream
    esRef.current?.close()

    setState({ sessionId: null, events: [], result: null, running: true, error: null })

    // 1. Start the pipeline
    // Special sentinel: use the fixed demo task endpoint
    const isDemo = question === '__demo__'
    let sessionId: string
    try {
      const res = await fetch(isDemo ? '/api/demo/run' : '/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(isDemo ? { mode } : { question, user_id: userId, mode }),
      })
      if (!res.ok) {
        const err = await res.json()
        setState(s => ({ ...s, running: false, error: err.detail ?? 'Request failed' }))
        return
      }
      const data = await res.json()
      sessionId = data.session_id
    } catch (e) {
      setState(s => ({ ...s, running: false, error: String(e) }))
      return
    }

    setState(s => ({ ...s, sessionId }))

    // 2. Subscribe to SSE stream
    const es = new EventSource(`/api/events/${sessionId}`)
    esRef.current = es

    es.onmessage = (e) => {
      const evt = JSON.parse(e.data)
      if (evt.type === '__done__') {
        setState(s => ({
          ...s,
          running: false,
          result: evt.result as PipelineResult,
        }))
        es.close()
        return
      }
      setState(s => ({ ...s, events: [...s.events, evt as AuditEvent] }))
    }

    es.onerror = () => {
      setState(s => ({ ...s, running: false }))
      es.close()
    }
  }, [])

  const reset = useCallback(() => {
    esRef.current?.close()
    setState({ sessionId: null, events: [], result: null, running: false, error: null })
  }, [])

  return { ...state, run, reset }
}
