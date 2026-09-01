import { useEffect, useState } from 'react'
import { api } from '../api'
import { FactorBreakdown, RiskBadge } from '../components/Risk'
import type { Alert } from '../types'
import { useAuth } from '../auth'

export default function Alerts() {
  const { user } = useAuth()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState<Alert | null>(null)
  const [caseTitle, setCaseTitle] = useState('')
  const [msg, setMsg] = useState('')

  const load = () => {
    const params = new URLSearchParams({ limit: '100' })
    if (statusFilter) params.set('status', statusFilter)
    api.get(`/alerts?${params}`).then((r) => setAlerts(r.data))
  }
  useEffect(load, [statusFilter])

  const canAct = user && user.role !== 'viewer'

  const setStatus = async (alert: Alert, status: string) => {
    await api.patch(`/alerts/${alert.id}/status`, { status })
    load()
    setSelected(null)
  }

  const openCase = async (alert: Alert) => {
    if (!caseTitle.trim()) return
    const { data } = await api.post('/cases', {
      title: caseTitle,
      customer_id: alert.customer_id,
      priority: alert.risk_level === 'critical' ? 'critical' : 'high',
      alert_ids: [alert.id],
      description: `Opened from alert #${alert.id} (risk ${alert.risk_score})`,
    })
    setMsg(`Case #${data.id} opened`)
    setCaseTitle('')
    load()
    setSelected(null)
  }

  return (
    <div>
      <h1>Alerts</h1>
      <div className="subtitle">Transactions whose explainable risk score crossed the alert threshold (60).</div>

      <div className="toolbar">
        <div>
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="open">open</option>
            <option value="in_review">in_review</option>
            <option value="escalated">escalated</option>
            <option value="dismissed">dismissed</option>
            <option value="resolved">resolved</option>
          </select>
        </div>
        {msg && <span className="success">{msg}</span>}
      </div>

      <div className="panel">
        <table>
          <thead>
            <tr><th>Created</th><th>Customer</th><th>Amount</th><th>Risk</th><th>Rules triggered</th><th>Status</th><th>Case</th></tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id} className="clickable" onClick={() => setSelected(a)}>
                <td className="muted">{new Date(a.created_at).toLocaleString()}</td>
                <td className="mono">{a.customer_id}</td>
                <td>{a.transaction ? `${a.transaction.amount.toFixed(2)} ${a.transaction.currency}` : '—'}</td>
                <td><RiskBadge level={a.risk_level} score={a.risk_score} /></td>
                <td>{a.triggered_rules.map((r) => r.rule_type).join(', ') || <span className="muted">model signal</span>}</td>
                <td><span className={`badge ${a.status === 'open' ? 'high' : a.status === 'resolved' ? 'green' : 'neutral'}`}>{a.status}</span></td>
                <td>{a.case_id ? <span className="badge blue">#{a.case_id}</span> : <span className="muted">—</span>}</td>
              </tr>
            ))}
            {alerts.length === 0 && <tr><td colSpan={7} className="muted">No alerts.</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h2>Alert #{selected.id}</h2>
              <RiskBadge level={selected.risk_level} score={selected.risk_score} />
            </div>
            <p className="muted">
              Customer {selected.customer_id}
              {selected.transaction && <> · txn {selected.transaction.transaction_id} · {selected.transaction.amount.toFixed(2)} {selected.transaction.currency} at {selected.transaction.merchant}</>}
            </p>
            <FactorBreakdown factors={selected.factors} />
            {canAct && (
              <div style={{ marginTop: 18, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
                <div className="row">
                  <button className="secondary small" onClick={() => setStatus(selected, 'in_review')}>Mark in review</button>
                  <button className="secondary small" onClick={() => setStatus(selected, 'escalated')}>Escalate</button>
                  <button className="danger small" onClick={() => setStatus(selected, 'dismissed')}>Dismiss</button>
                </div>
                {!selected.case_id && (
                  <div className="row" style={{ marginTop: 12 }}>
                    <input placeholder="Case title…" value={caseTitle} onChange={(e) => setCaseTitle(e.target.value)} style={{ flex: 1 }} />
                    <button className="small" onClick={() => openCase(selected)}>Open case</button>
                  </div>
                )}
              </div>
            )}
            <div style={{ marginTop: 14, textAlign: 'right' }}>
              <button className="secondary" onClick={() => setSelected(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
