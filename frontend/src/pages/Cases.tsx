import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Case, User } from '../types'
import { useAuth } from '../auth'
import { RiskBadge } from '../components/Risk'

const CASE_STATUSES = [
  'open', 'assigned', 'investigating', 'pending_info',
  'closed_confirmed_fraud', 'closed_false_positive', 'closed_inconclusive',
]

export default function Cases() {
  const { user } = useAuth()
  const [cases, setCases] = useState<Case[]>([])
  const [selected, setSelected] = useState<Case | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [note, setNote] = useState('')

  const load = () => api.get('/cases?limit=100').then((r) => setCases(r.data))
  useEffect(() => {
    load()
    if (user?.role === 'admin') api.get('/auth/users').then((r) => setUsers(r.data))
  }, [])

  const canAct = user && user.role !== 'viewer'

  const refreshSelected = async (id: number) => {
    const { data } = await api.get(`/cases/${id}`)
    setSelected(data)
    load()
  }

  const update = async (id: number, patch: Record<string, unknown>) => {
    await api.patch(`/cases/${id}`, patch)
    refreshSelected(id)
  }

  const addNote = async (id: number) => {
    if (!note.trim()) return
    await api.post(`/cases/${id}/notes`, { body: note })
    setNote('')
    refreshSelected(id)
  }

  return (
    <div>
      <h1>Case Management</h1>
      <div className="subtitle">Open, assign, investigate, annotate and close fraud investigations.</div>

      <div className="panel">
        <table>
          <thead>
            <tr><th>#</th><th>Title</th><th>Customer</th><th>Priority</th><th>Status</th><th>Assigned to</th><th>Updated</th></tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.id} className="clickable" onClick={() => setSelected(c)}>
                <td>{c.id}</td>
                <td>{c.title}</td>
                <td className="mono">{c.customer_id}</td>
                <td><span className={`badge ${c.priority === 'critical' ? 'critical' : c.priority === 'high' ? 'high' : 'medium'}`}>{c.priority}</span></td>
                <td><span className={`badge ${c.status.startsWith('closed') ? 'neutral' : 'blue'}`}>{c.status}</span></td>
                <td>{c.assigned_to?.username ?? <span className="muted">unassigned</span>}</td>
                <td className="muted">{new Date(c.updated_at).toLocaleString()}</td>
              </tr>
            ))}
            {cases.length === 0 && <tr><td colSpan={7} className="muted">No cases. Open one from an alert.</td></tr>}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Case #{selected.id}: {selected.title}</h2>
            <p className="muted">{selected.description || 'No description.'}</p>
            <div className="row" style={{ marginBottom: 14 }}>
              <span className="badge blue">{selected.status}</span>
              <span className={`badge ${selected.priority === 'critical' ? 'critical' : 'high'}`}>{selected.priority}</span>
              <span className="muted">customer {selected.customer_id}</span>
              <span className="muted">opened by {selected.opened_by.username}</span>
              {selected.closed_at && <span className="muted">closed {new Date(selected.closed_at).toLocaleString()}</span>}
            </div>

            {canAct && !selected.status.startsWith('closed') && (
              <div className="row" style={{ marginBottom: 14 }}>
                <div>
                  <label>Status</label>
                  <select value={selected.status} onChange={(e) => update(selected.id, { status: e.target.value })}>
                    {CASE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                {users.length > 0 && (
                  <div>
                    <label>Assign to</label>
                    <select value={selected.assigned_to?.id ?? ''} onChange={(e) => update(selected.id, { assigned_to_id: Number(e.target.value) })}>
                      <option value="" disabled>choose…</option>
                      {users.map((u) => <option key={u.id} value={u.id}>{u.username} ({u.role})</option>)}
                    </select>
                  </div>
                )}
              </div>
            )}

            <h2>Linked alerts</h2>
            {selected.alerts.length === 0 && <div className="muted">None.</div>}
            {selected.alerts.map((a) => (
              <div key={a.id} className="note">
                <div className="meta">Alert #{a.id} · {a.status}</div>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <span>{a.transaction ? `${a.transaction.amount.toFixed(2)} ${a.transaction.currency} @ ${a.transaction.merchant}` : a.customer_id}</span>
                  <RiskBadge level={a.risk_level} score={a.risk_score} />
                </div>
              </div>
            ))}

            <h2 style={{ marginTop: 16 }}>Investigation notes</h2>
            {selected.notes.map((n) => (
              <div key={n.id} className="note">
                <div className="meta">{n.author.username} · {new Date(n.created_at).toLocaleString()}</div>
                {n.body}
              </div>
            ))}
            {selected.notes.length === 0 && <div className="muted">No notes yet.</div>}
            {canAct && (
              <div className="row" style={{ marginTop: 10 }}>
                <textarea rows={2} style={{ flex: 1 }} placeholder="Add investigation note…"
                  value={note} onChange={(e) => setNote(e.target.value)} />
                <button onClick={() => addNote(selected.id)}>Add note</button>
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
