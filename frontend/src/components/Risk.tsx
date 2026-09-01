import type { RiskFactors } from '../types'

export function RiskBadge({ level, score }: { level: string | null; score: number | null }) {
  if (level == null || score == null) return <span className="badge neutral">n/a</span>
  return <span className={`badge ${level}`}>{level} · {score.toFixed(0)}</span>
}

export function FactorBreakdown({ factors }: { factors: RiskFactors }) {
  return (
    <div>
      <h2>Score composition</h2>
      {factors.components.map((c) => (
        <div key={c.name} style={{ marginBottom: 10 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span>{c.name.replace(/_/g, ' ')} <span className="muted">(weight {(c.weight * 100).toFixed(0)}%)</span></span>
            <b>+{c.contribution.toFixed(1)} pts</b>
          </div>
          <div className="factor-bar"><div style={{ width: `${Math.min(c.contribution, 100)}%` }} /></div>
        </div>
      ))}

      <h2 style={{ marginTop: 18 }}>Triggered rules</h2>
      {factors.rule_hits.length === 0 && <div className="muted">No rules triggered.</div>}
      {factors.rule_hits.map((h) => (
        <div key={h.rule_id + h.detail} className="note">
          <div className="meta">{h.rule_name} · severity {(h.severity * 100).toFixed(0)}%</div>
          {h.detail}
        </div>
      ))}

      <h2 style={{ marginTop: 18 }}>Model signals</h2>
      <div className="row">
        <span className="badge blue">
          supervised: {factors.model_signals.supervised_fraud_probability != null
            ? `${(factors.model_signals.supervised_fraud_probability * 100).toFixed(1)}% fraud prob.`
            : 'no model trained'}
        </span>
        <span className="badge blue">
          anomaly: {factors.model_signals.anomaly_score != null
            ? factors.model_signals.anomaly_score.toFixed(3)
            : 'no model trained'}
        </span>
      </div>

      <h2 style={{ marginTop: 18 }}>Behavioral context</h2>
      <table>
        <tbody>
          {Object.entries(factors.behavioral_context).map(([k, v]) => (
            <tr key={k}>
              <td className="muted">{k.replace(/_/g, ' ')}</td>
              <td><b>{String(v)}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
