import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Rule } from '../types'
import { useAuth } from '../auth'

export default function Rules() {
  const { user } = useAuth()
  const [rules, setRules] = useState<Rule[]>([])
  const [editing, setEditing] = useState<Rule | null>(null)
  const [paramsText, setParamsText] = useState('')
  const [severity, setSeverity] = useState(0.5)
  const [error, setError] = useState('')

  const load = () => api.get('/rules').then((r) => setRules(r.data))
  useEffect(() => { load() }, [])

  const isAdmin = user?.role === 'admin'

  const toggle = async (rule: Rule) => {
    await api.patch(`/rules/${rule.id}`, { enabled: !rule.enabled })
    load()
  }

  const startEdit = (rule: Rule) => {
    setEditing(rule)
    setParamsText(JSON.stringify(rule.parameters, null, 2))
    setSeverity(rule.severity)
    setError('')
  }

  const save = async () => {
    if (!editing) return
    let params: Record<string, unknown>
    try {
      params = JSON.parse(paramsText)
    } catch {
      setError('Parameters must be valid JSON'); return
    }
    try {
      await api.patch(`/rules/${editing.id}`, { parameters: params, severity })
      setEditing(null)
      load()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Save failed')
    }
  }

  return (
    <div>
      <h1>Rule Engine</h1>
      <div className="subtitle">
        Rules are stored in the database and fully configurable — thresholds, severity and enablement
        are data, not code. {isAdmin ? 'You can edit them as admin.' : 'Sign in as admin to edit.'}
      </div>

      <div className="panel">
        <table>
          <thead>
            <tr><th>Rule</th><th>Type</th><th>Parameters</th><th>Severity</th><th>Enabled</th>{isAdmin && <th></th>}</tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id}>
                <td>
                  <b>{r.name}</b>
                  <div className="muted" style={{ fontSize: 12 }}>{r.description}</div>
                </td>
                <td><span className="badge blue">{r.rule_type}</span></td>
                <td className="mono">{Object.entries(r.parameters).map(([k, v]) => `${k}=${v}`).join(', ')}</td>
                <td>{(r.severity * 100).toFixed(0)}%</td>
                <td>
                  <span className={`badge ${r.enabled ? 'green' : 'neutral'}`}>{r.enabled ? 'enabled' : 'disabled'}</span>
                </td>
                {isAdmin && (
                  <td>
                    <div className="row">
                      <button className="secondary small" onClick={() => startEdit(r)}>Edit</button>
                      <button className={`small ${r.enabled ? 'danger' : ''}`} onClick={() => toggle(r)}>
                        {r.enabled ? 'Disable' : 'Enable'}
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="modal-overlay" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit rule: {editing.name}</h2>
            <div className="field">
              <label>Parameters (JSON)</label>
              <textarea rows={7} style={{ width: '100%' }} className="mono"
                value={paramsText} onChange={(e) => setParamsText(e.target.value)} />
            </div>
            <div className="field">
              <label>Severity: {(severity * 100).toFixed(0)}%</label>
              <input type="range" min={0} max={1} step={0.05} value={severity}
                onChange={(e) => setSeverity(Number(e.target.value))} style={{ width: '100%' }} />
            </div>
            {error && <div className="error">{error}</div>}
            <div className="row" style={{ justifyContent: 'end' }}>
              <button className="secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button onClick={save}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
