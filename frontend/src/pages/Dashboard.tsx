import { useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api'
import type { Summary } from '../types'

const LEVEL_COLORS: Record<string, string> = {
  low: '#2fbf71', medium: '#e8b93c', high: '#f08c3a', critical: '#e5484d',
}

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [dist, setDist] = useState<{ level: string; count: number }[]>([])
  const [trend, setTrend] = useState<any[]>([])
  const [topCustomers, setTopCustomers] = useState<any[]>([])
  const [caseStatus, setCaseStatus] = useState<any[]>([])
  const [alertStatus, setAlertStatus] = useState<any[]>([])

  useEffect(() => {
    api.get('/analytics/summary').then((r) => setSummary(r.data))
    api.get('/analytics/risk-distribution').then((r) => setDist(r.data))
    api.get('/analytics/volume-trend?days=45').then((r) => setTrend(r.data))
    api.get('/analytics/high-risk-customers').then((r) => setTopCustomers(r.data))
    api.get('/analytics/case-status').then((r) => setCaseStatus(r.data))
    api.get('/analytics/alert-status').then((r) => setAlertStatus(r.data))
  }, [])

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="subtitle">Real-time fraud operations overview</div>
      <div className="synthetic-banner">
        ⚠ Development environment — all data shown is SYNTHETIC. No real payment credentials are used.
      </div>

      <div className="cards">
        <Card label="Transactions" value={summary?.total_transactions?.toLocaleString()} />
        <Card label="Txns (24h)" value={summary?.transactions_24h?.toLocaleString()} />
        <Card label="Total volume" value={summary ? `$${summary.total_volume.toLocaleString()}` : '—'} />
        <Card label="Open alerts" value={summary?.open_alerts} />
        <Card label="Open cases" value={summary?.open_cases} />
        <Card label="Avg risk score" value={summary?.avg_risk_score} />
      </div>

      <div className="grid2">
        <div className="panel">
          <h2>Transaction volume &amp; count trend</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trend}>
              <CartesianGrid stroke="#24314f" strokeDasharray="3 3" />
              <XAxis dataKey="day" stroke="#8b9ab5" fontSize={11} />
              <YAxis yAxisId="l" stroke="#8b9ab5" fontSize={11} />
              <YAxis yAxisId="r" orientation="right" stroke="#8b9ab5" fontSize={11} />
              <Tooltip contentStyle={{ background: '#182440', border: '1px solid #24314f' }} />
              <Legend />
              <Line yAxisId="l" type="monotone" dataKey="volume" stroke="#4f8cff" dot={false} name="Volume" />
              <Line yAxisId="r" type="monotone" dataKey="count" stroke="#2fbf71" dot={false} name="Count" />
              <Line yAxisId="r" type="monotone" dataKey="high_risk" stroke="#e5484d" dot={false} name="High-risk" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h2>Risk distribution</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={dist} dataKey="count" nameKey="level" innerRadius={55} outerRadius={90} label>
                {dist.map((d) => <Cell key={d.level} fill={LEVEL_COLORS[d.level]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#182440', border: '1px solid #24314f' }} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h2>High-risk customers</h2>
          <table>
            <thead>
              <tr><th>Customer</th><th>Max risk</th><th>Avg risk</th><th>Txns</th><th>High-risk txns</th></tr>
            </thead>
            <tbody>
              {topCustomers.map((c) => (
                <tr key={c.customer_id}>
                  <td className="mono">{c.customer_id}</td>
                  <td><span className={`badge ${c.max_risk >= 80 ? 'critical' : c.max_risk >= 60 ? 'high' : 'medium'}`}>{c.max_risk}</span></td>
                  <td>{c.avg_risk}</td>
                  <td>{c.txn_count}</td>
                  <td>{c.high_risk_txns}</td>
                </tr>
              ))}
              {topCustomers.length === 0 && <tr><td colSpan={5} className="muted">No data yet.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h2>Case &amp; alert status</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={[...caseStatus.map((c) => ({ ...c, kind: 'case' })), ...alertStatus.map((a) => ({ ...a, kind: 'alert' }))]}>
              <CartesianGrid stroke="#24314f" strokeDasharray="3 3" />
              <XAxis dataKey="status" stroke="#8b9ab5" fontSize={10} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis stroke="#8b9ab5" fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#182440', border: '1px solid #24314f' }} />
              <Bar dataKey="count" fill="#4f8cff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
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
