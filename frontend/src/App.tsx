import { useState } from 'react'
import Ask from './Ask'
import Extract from './Extract'
import Quality from './Quality'

const TABS = [
  { id: 'ask', label: 'Ask', hint: 'Answers with sources, or an honest "not found"' },
  { id: 'extract', label: 'Extract', hint: 'Report PDF → checked table' },
  { id: 'quality', label: 'Quality', hint: 'How we know it works' },
] as const
type Tab = (typeof TABS)[number]['id']

export default function App() {
  const [tab, setTab] = useState<Tab>('ask')
  return (
    <div className="shell">
      <header>
        <div className="brand">
          <span className="logo">RD</span>
          <div>
            <h1>Research Desk</h1>
            <p>AI assistant over a library of market-research reports</p>
          </div>
        </div>
        <nav>
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)} title={t.hint}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {/* keep every tab mounted so switching doesn't lose results */}
        <div hidden={tab !== 'ask'}><Ask /></div>
        <div hidden={tab !== 'extract'}><Extract /></div>
        <div hidden={tab !== 'quality'}><Quality /></div>
      </main>
      <footer>Prototype on 6 fictional reports · hybrid search (BM25 + embeddings + reranker) · Gemini tool-calling agent</footer>
    </div>
  )
}
