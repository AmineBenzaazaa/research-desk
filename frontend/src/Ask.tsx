import { useState } from 'react'
import { api, type AskResult, type Passage } from './api'

const EXAMPLES = [
  'How many reports were published in 2026?',
  'What was the actual size of the Saudi digital health market in 2025?',
  'What risks does the GCC EV charging report highlight?',
  'How much fintech funding did Morocco raise in the first nine months of 2026?',
  'What is the population of Japan?',
]

function Citations({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[?AR-[A-Z]+-\d+\]?|\*\*[^*]+\*\*)/g).map((part, i) =>
        /^\[?AR-[A-Z]+-\d+\]?$/.test(part) ? <span key={i} className="cite">{part.replace(/[[\]]/g, '')}</span>
          : part.startsWith('**') ? <b key={i}>{part.slice(2, -2)}</b> : part,
      )}
    </>
  )
}

function StepView({ step }: { step: AskResult['trace'][number] }) {
  const r = step.result as { passages?: Passage[]; rows?: unknown[][]; columns?: string[]; error?: string; note?: string }
  return (
    <div className="step">
      <div className="step-head">
        <span className="badge">step {step.step}</span>
        <code>{step.tool}</code>
        <span className="args">{String(Object.values(step.args)[0] ?? '')}</span>
      </div>
      {r.error && <div className="warn">Error returned to the model: {r.error}</div>}
      {r.note && <div className="muted">{r.note}</div>}
      {r.rows && (
        <table className="mini">
          <thead><tr>{r.columns?.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{r.rows.slice(0, 8).map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody>
        </table>
      )}
      {r.passages?.map((p, i) => (
        <div key={i} className="passage">
          <div><span className="cite">{p.report_id}</span> <span className="muted">published {p.published} · rerank {p.score}</span>
            {p.score < 0 && <span className="pill" title="Below the threshold: kept as context because the best passage passed">weak</span>}</div>
          <p>{p.text}</p>
        </div>
      ))}
    </div>
  )
}

export default function Ask() {
  const [q, setQ] = useState('')
  const [res, setRes] = useState<AskResult | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(question = q) {
    if (question.trim().length < 3) return
    setQ(question); setLoading(true); setErr(''); setRes(null)
    try { setRes(await api.ask(question)) } catch (e) { setErr((e as Error).message) } finally { setLoading(false) }
  }

  return (
    <section>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about the reports…" maxLength={500} />
        <button disabled={loading}>{loading ? 'Thinking…' : 'Ask'}</button>
      </form>
      <div className="chips">
        {EXAMPLES.map((e) => <button key={e} className="chip" onClick={() => submit(e)} disabled={loading}>{e}</button>)}
      </div>
      {err && <div className="card warn">{err}</div>}
      {res && (
        <div className="grid2">
          <div className={`card answer ${res.refused ? 'refused' : ''}`}>
            <h3>{res.refused ? 'Not in the reports' : 'Answer'}</h3>
            <p><Citations text={res.answer} /></p>
            <div className="muted small">
              {res.llm_calls} LLM call{res.llm_calls > 1 ? 's' : ''}{res.cached_calls ? ` (${res.cached_calls} cached)` : ''} · {res.trace.length} tool call{res.trace.length === 1 ? '' : 's'} · {(res.ms / 1000).toFixed(1)}s
            </div>
          </div>
          <div className="card">
            <h3>How it got there</h3>
            {res.trace.length === 0 && <p className="muted">No tool was called.</p>}
            {res.trace.map((s, i) => <StepView key={i} step={s} />)}
          </div>
        </div>
      )}
    </section>
  )
}
