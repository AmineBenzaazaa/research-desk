import { useEffect, useState } from 'react'
import { api, type Quality as Q } from './api'

const LABELS: Record<string, [string, string]> = {
  hit_rate: ['Hit rate @3', 'Right passage in the top 3'],
  mrr: ['MRR', '1 = right passage always ranked first'],
  answerable_recall: ['Answered', 'Answerable questions not wrongly refused'],
  unanswerable_rejected: ['Refused', 'Out-of-scope questions correctly refused'],
  vague_hit_rate: ['Vague questions', 'Hit rate on short / name-only questions'],
  ms_per_query: ['Latency', 'ms per search, on a laptop CPU'],
}
const BEFORE: Record<string, number> = { hit_rate: 1, mrr: 0.95, answerable_recall: 0.9, unanswerable_rejected: 0.86, vague_hit_rate: 0.5, ms_per_query: 7 }

const fmt = (k: string, v: number) => (k === 'ms_per_query' ? `${v}` : k === 'mrr' ? v.toFixed(2) : `${Math.round(v * 100)}%`)

export default function Quality() {
  const [q, setQ] = useState<Q | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  function load(refresh = false) {
    setLoading(true); setErr('')
    api.quality(refresh).then(setQ).catch((e) => setErr(e.message)).finally(() => setLoading(false))
  }
  useEffect(() => load(), [])

  if (err) return <div className="card warn">{err}</div>
  if (!q) return <div className="card muted">Running {loading ? 'the test set…' : ''}</div>

  return (
    <section>
      <div className="row between">
        <div className={`gate ${q.passed ? 'ok' : 'bad'}`}>{q.passed ? '✓ Quality gate passed' : '✗ Quality gate failed'}</div>
        <button onClick={() => load(true)} disabled={loading}>{loading ? 'Running…' : 'Re-run tests'}</button>
      </div>
      <div className="tiles">
        {Object.entries(LABELS).map(([k, [label, hint]]) => (
          <div key={k} className="tile" title={hint}>
            <div className="tile-label">{label}</div>
            <div className="tile-value">{fmt(k, q.summary[k])}{k === 'ms_per_query' && <small> ms</small>}</div>
            <div className="muted small">before: {fmt(k, BEFORE[k])}{k === 'ms_per_query' ? ' ms' : ''} (embeddings only)</div>
          </div>
        ))}
      </div>
      <div className="card">
        <h3>Every test question</h3>
        <p className="muted small">Refuse/answer is decided on the best reranker score (threshold {q.threshold}). No LLM calls, so this runs free on every change.</p>
        <table>
          <thead><tr><th>Type</th><th>Question</th><th>Expected</th><th>Rank</th><th>Best score</th><th>Result</th></tr></thead>
          <tbody>
            {q.rows.map((r, i) => {
              const ok = r.kind === 'unanswerable' ? !r.answered : r.rank !== null && r.answered
              return (
                <tr key={i}>
                  <td><span className="pill">{r.kind}</span></td>
                  <td>{r.question}</td>
                  <td>{r.expected ?? <span className="muted">should refuse</span>}</td>
                  <td>{r.rank ?? '–'}</td>
                  <td className="num">{r.top_score.toFixed(2)}</td>
                  <td>{ok ? <span className="pill ok">pass</span> : <span className="pill bad">fail</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
