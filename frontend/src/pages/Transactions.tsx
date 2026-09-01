import { useEffect, useState } from 'react'
import { api } from '../api'
import { FactorBreakdown, RiskBadge } from '../components/Risk'
import type { Transaction } from '../types'
import { useAuth } from '../auth'

export default function Transactions() {
  const { user } = useAuth()
  const [txns, setTxns] = useState<Transaction[]>([])
  const [customer, setCustomer] = useState('')
  const [level, setLevel] = useState('')
  const [selected, setSelected] = useState<Transaction | null>(null)
  const [uploadMsg, setUploadMsg] = useState('')

  const load = () => {
    const params = new URLSearchParams({ limit: '100' })
    if (customer) params.set('customer_id', customer)
    if (level) params.set('risk_level', level)
    api.get(`/transactions?${params}`).then((r) => setTxns(r.data))
  }
  useEffect(load, [level])

  const upload = async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    setUploadMsg('Uploading & scoring…')
    try {
      const { data } = await api.post('/transactions/batch', form)
      setUploadMsg(`Accepted ${data.accepted}, rejected ${data.rejected}, alerts created ${data.alerts_created}`)
      load()
    } catch (e: any) {
      setUploadMsg(e.response?.data?.detail || 'Upload failed')
    }
  }

  const canIngest = user && user.role !== 'viewer'

  return (
    <div>
      <h1>Transactions</h1>
      <div className="subtitle">Every transaction is validated, feature-engineered and risk-scored on ingestion.</div>

      <div className="toolbar">
        <div>
          <label>Customer ID</label>
          <input value={customer} onChange={(e) => setCustomer(e.target.value)} placeholder="SYN-CUST-0001" />
        </div>
        <div>
          <label>Risk level</label>
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="">All</option>
            <option>low</option><option>medium</option><option>high</option><option>critical</option>
          </select>
        </div>
        <button className="secondary" onClick={load}>Filter</button>
        {canIngest && (
          <label className="btn" style={{ color: '#fff', cursor: 'pointer', marginBottom: 0 }}>
            Upload CSV
            <input type="file" accept=".csv" style={{ display: 'none' }}
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        )}
        {uploadMsg && <span className="muted">{uploadMsg}</span>}
      </div>

      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Transaction</th><th>Customer</th><th>Amount</th>
              <th>Merchant</th><th>Location</th><th>Channel</th><th>Status</th><th>Risk</th><th>Source</th>
            </tr>
          </thead>
          <tbody>
            {txns.map((t) => (
              <tr key={t.id} className="clickable" onClick={() => setSelected(t)}>
                <td className="muted">{new Date(t.timestamp).toLocaleString()}</td>
                <td className="mono">{t.transaction_id.slice(0, 18)}…</td>
                <td className="mono">{t.customer_id}</td>
                <td><b>{t.amount.toFixed(2)}</b> <span className="muted">{t.currency}</span></td>
                <td>{t.merchant}</td>
                <td>{t.location}</td>
                <td>{t.channel}</td>
                <td><span className={`badge ${t.status === 'approved' ? 'green' : 'neutral'}`}>{t.status}</span></td>
                <td><RiskBadge level={t.risk_level} score={t.risk_score} /></td>
                <td><span className={`badge ${t.data_source === 'synthetic' ? 'medium' : 'neutral'}`}>{t.data_source}</span></td>
              </tr>
            ))}
            {txns.length === 0 && <tr><td colSpan={10} className="muted">No transactions. Seed synthetic data from the ML Models page (admin) or upload a CSV.</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h2>Transaction {selected.transaction_id}</h2>
              <RiskBadge level={selected.risk_level} score={selected.risk_score} />
            </div>
            <p className="muted">
              {selected.customer_id} · {selected.amount.toFixed(2)} {selected.currency} · {selected.merchant} ·{' '}
              {selected.location} · {selected.channel} · device {selected.device}
            </p>
            {selected.risk_factors
              ? <FactorBreakdown factors={selected.risk_factors} />
              : <div className="muted">No factor data.</div>}
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <button className="secondary" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
