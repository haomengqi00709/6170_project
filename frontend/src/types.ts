export interface AuditEvent {
  type: string
  agent: string
  message: string
  data: Record<string, unknown>
  ts: string
}

export interface EmailItem {
  to: string
  subject: string
  body: string
}

export interface EmailAction {
  type: string
  emails: EmailItem[]
}

export interface PipelineResult {
  session_id: string
  question: string
  answer: string
  action_type: string
  cited_sources: string[]
  session_status: string
  hitl_result: {
    status: string
    tier: number
    review_id: number | null
  } | null
  email_action?: EmailAction | null
  blocked_recipients?: string[]
}

export interface Review {
  id: number
  session_id: string
  action_type: string
  action_detail: string
  reasoning_chain: unknown[]
  risk_tier: number
  status: string
  reviewer_decision: string | null
  reviewer_note: string | null
  created_at: string
  reviewed_at: string | null
}

export interface Session {
  session_id: string
  user_id: string
  question: string
  status: string
  started_at: string
  ended_at: string | null
}

export interface User {
  user_id: string
  name: string
  level: string
  department: string
}
