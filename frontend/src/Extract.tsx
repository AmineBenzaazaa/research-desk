import { useEffect, useState } from 'react'
import { api, type Extraction } from './api'

function toCsv(x: Extraction) {
  const head = ['report_id', 'name', 'value', 'unit', 'year', 'is_forecast', 'checks_ok', 'source_quote']
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const rows = x.metrics.map((m) =>
    [x.report.report_id, m.name, m.value, m.unit, m.year, m.is_forecast, m.quote_in_doc && m.value_in_quote, m.source_quote].map(esc).join(','))
  return [head.join(','), ...rows].join('\n')
}

export default function Extract() {
  const [files, setFiles] = useState<string[]>([])
  const [res, setRes] = useState<Extraction | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => { api.reports().then((r) => setFiles(r.files)).catch(() => {}) }, [])

  async function run(p: Promise<Extraction>) {
    setLoading(true); setErr(''); setRes(null)
    try { setRes(await p) } catch (e) { setErr((e as Error).message) } finally { setLoading(false) }
  }

  function download() {
    if (!res) return
    const url = URL.createObjectURL(new Blob([toCsv(res)], { type: 'text/csv' }))
    Object.assign(document.createElement('a'), { href: url, download: `${res.report.report_id}.csv` }).click()
    URL.revokeObjectURL(url)
  }

  return (
    <section>
      <div className="card">
        <h3>Turn a report into data</h3>
        <p className="muted">The model fills a strict schema. Then code checks every number: is the quote really in the PDF, and is the number really in the quote?</p>
        <div className="row">
          <label className="upload">
            Upload PDF
            <input type="file" accept="application/pdf" hidden onChange={(e) => e.target.files?.[0] && run(api.extractFile(e.target.files[0]))} />
          </label>
          <span className="muted">or try one:</span>
          <select disabled={loading} defaultValue="" onChange={(e) => e.target.value && run(api.extractSample(e.target.value))}>
            <option value="" disabled>Sample report…</option>
            {files.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          {loading && <span className="muted">Extracting…</span>}
        </div>
      </div>
      {err && <div className="card warn">{err}</div>}
      {res && (
        <div className="card">
          <div className="row between">
            <div>
              <h3>{res.report.title}</h3>
              <div className="muted">
                <span className="cite">{res.report.report_id}</span> · published {res.report.published_date} · {res.report.regions.join(', ')}
                {res.report.supersedes && <> · <b>replaces {res.report.supersedes}</b></>}
              </div>
            </div>
            <div className="row">
              <span className={`pill ${res.checks_passed === res.checks_total ? 'ok' : 'bad'}`}>
                {res.checks_passed}/{res.checks_total} numbers verified
              </span>
              <button onClick={download}>Download CSV</button>
            </div>
          </div>
          {res.report.suspicious_instructions && (
            <div className="warn">⚠ Hidden instruction found in this document (flagged, not followed): “{res.report.suspicious_instructions}”</div>
          )}
          <table>
            <thead><tr><th>Metric</th><th>Value</th><th>Year</th><th>Type</th><th>Checks</th><th>Source quote</th></tr></thead>
            <tbody>
              {res.metrics.map((m, i) => (
                <tr key={i}>
                  <td>{m.name}</td>
                  <td className="num">{m.value.toLocaleString()} <span className="muted">{m.unit}</span></td>
                  <td>{m.year ?? '–'}</td>
                  <td>{m.is_forecast ? <span className="pill">forecast</span> : 'actual'}</td>
                  <td>{m.quote_in_doc && m.value_in_quote ? <span className="pill ok">✓</span> : <span className="pill bad" title={`quote in doc: ${m.quote_in_doc}, value in quote: ${m.value_in_quote}`}>review</span>}</td>
                  <td className="quote">{m.source_quote}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {res.cached && <div className="muted small">Served from cache: same model + rules + schema + document → no API call.</div>}
        </div>
      )}
    </section>
  )
}
