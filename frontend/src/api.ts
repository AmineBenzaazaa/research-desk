export type Passage = { report_id: string; published: string; score: number; text: string }
export type Step = { step: number; tool: string; args: Record<string, unknown>; result: Record<string, unknown> }
export type AskResult = {
  answer: string; refused: boolean; cited: string[]; trace: Step[]
  llm_calls: number; cached_calls: number; ms: number
}
export type MetricRow = {
  name: string; value: number; unit: string; year: number | null; is_forecast: boolean
  source_quote: string; quote_in_doc: boolean; value_in_quote: boolean
}
export type Extraction = {
  report: { report_id: string; title: string; published_date: string; regions: string[]; supersedes: string | null; suspicious_instructions: string | null }
  metrics: MetricRow[]; cached: boolean; checks_passed: number; checks_total: number
}
export type QualityRow = { kind: string; question: string; expected: string | null; rank: number | null; top_score: number; answered: boolean }
export type Quality = {
  summary: Record<string, number>; gate: Record<string, { min: number; value: number; ok: boolean }>
  passed: boolean; threshold: number; rows: QualityRow[]
}

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`)
  return body as T
}

export const api = {
  ask: (question: string) =>
    call<AskResult>('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) }),
  reports: () => call<{ files: string[] }>('/api/reports'),
  extractSample: (name: string) => call<Extraction>(`/api/extract/sample/${encodeURIComponent(name)}`, { method: 'POST' }),
  extractFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return call<Extraction>('/api/extract', { method: 'POST', body: form })
  },
  quality: (refresh = false) => call<Quality>(`/api/quality${refresh ? '?refresh=true' : ''}`),
}
