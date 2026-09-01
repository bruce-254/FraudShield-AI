import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'

export default function Reports() {
  const { user } = useAuth()
  const [days, setDays] = useState(30)
  const [report, setReport] = useState<any>(null)
  const [auditLog, setAuditLog] = useState<any[]>([])

  const canExport = user && user.role !== 'viewer'

  const load = () => {
    api.get(`/reports/fraud-summary?days=${days}`).then((r) => setReport(r.data))
    if (canExport) api.get('/reports/audit-log?limit=50').then((r) => setAuditLog(r.data))
  }
  useEffect(load, [days])

  const downloadCsv = async () => {
    const resp = await api.get(`/reports/transactions.csv?days=${days}`, { responseType: 'blob' })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'transactions.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <h1>Reports</h1>
      <div className="subtitle">Operational fraud reporting and audit trail.</div>

      <div className="toolbar">
        <div>
          <label>Period (days)</label>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[7, 30, 60, 90].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        {canExport && <button onClick={downloadCsv}>Export transactions CSV</button>}
      </div>

      {report && (
        <>
          <div className="cards">
            <Card label="Transactions" value={report.transactions.toLocaleString()} />
            <Card label="Flagged high/critical" value={report.flagged_high_or_critical} />
            <Card label="Flagged rate" value={`${(report.flagged_rate * 100).toFixed(2)}%`} />
            <Card label="Flagged volume" value={`$${report.flagged_volume.toLocaleString()}`} />
            <Card label="Alerts created" value={report.alerts_created} />
            <Card label="Cases opened" value={report.cases_opened} />
            <Card label="Confirmed fraud" value={report.cases_confirmed_fraud} />
          </div>

          <div className="panel">
            <h2>Most-triggered rules</h2>
            <table>
              <thead><tr><th>Rule</th><th>Hits</th></tr></thead>
              <tbody>
                {report.top_triggered_rules.map((r: any) => (
                  <tr key={r.rule}><td>{r.rule}</td><td><b>{r.hits}</b></td></tr>
                ))}
                {report.top_triggered_rules.length === 0 && <tr><td colSpan={2} className="muted">No rule hits in period.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {canExport && (
        <div className="panel">
          <h2>Audit log (latest 50)</h2>
          <table>
            <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Resource</th></tr></thead>
            <tbody>
              {auditLog.map((e) => (
                <tr key={e.id}>
                  <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                  <td>{e.username}</td>
                  <td><span className="badge blue">{e.action}</span></td>
                  <td className="mono">{e.resource}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Card({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
    </div>
  )
}
