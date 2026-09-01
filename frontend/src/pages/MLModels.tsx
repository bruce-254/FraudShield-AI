import { useEffect, useState } from 'react'
import { api } from '../api'
import type { MLModel } from '../types'
import { useAuth } from '../auth'

export default function MLModels() {
  const { user } = useAuth()
  const [models, setModels] = useState<MLModel[]>([])
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const load = () => api.get('/ml/models').then((r) => setModels(r.data))
  useEffect(() => { load() }, [])

  const canTrain = user && user.role !== 'viewer'
  const isAdmin = user?.role === 'admin'

  const train = async (kind: 'supervised' | 'anomaly') => {
    setBusy(kind); setError(''); setMsg('')
    try {
      const { data } = await api.post('/ml/train', { model_kind: kind })
      setMsg(`Trained ${data.algorithm} on ${data.trained_on} transactions.`)
      load()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Training failed')
    } finally {
      setBusy('')
    }
  }

  const seed = async () => {
    setBusy('seed'); setError(''); setMsg('')
    try {
      const { data } = await api.post('/admin/seed-synthetic?customers=40&days=45')
      setMsg(`Seeded synthetic data: ${data.accepted} accepted, ${data.alerts_created} alerts created.`)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Seeding failed')
    } finally {
      setBusy('')
    }
  }

  return (
    <div>
      <h1>ML Models</h1>
      <div className="subtitle">
        Supervised classification (RandomForest) on labeled data; IsolationForest anomaly detection when
        labels are unavailable. All metrics are computed on a genuine held-out test split — nothing is fabricated.
      </div>

      <div className="row" style={{ marginBottom: 18 }}>
        {isAdmin && <button className="secondary" disabled={!!busy} onClick={seed}>
          {busy === 'seed' ? 'Seeding…' : 'Seed synthetic data (admin)'}
        </button>}
        {canTrain && <>
          <button disabled={!!busy} onClick={() => train('supervised')}>
            {busy === 'supervised' ? 'Training…' : 'Train supervised classifier'}
          </button>
          <button disabled={!!busy} onClick={() => train('anomaly')}>
            {busy === 'anomaly' ? 'Training…' : 'Train anomaly detector'}
          </button>
        </>}
      </div>
      {msg && <div className="success">{msg}</div>}
      {error && <div className="error">{error}</div>}

      {models.map((m) => <ModelCard key={m.id} model={m} />)}
      {models.length === 0 && <div className="panel muted">No models trained yet. Seed synthetic data, then train.</div>}
    </div>
  )
}

function ModelCard({ model }: { model: MLModel }) {
  const m = model.metrics
  const cm: number[][] | undefined = m.confusion_matrix || m.confusion_matrix_vs_labels
  return (
    <div className="panel">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>
          {model.algorithm} <span className="muted">({model.model_kind})</span>{' '}
          {model.is_active && <span className="badge green">active</span>}
        </h2>
        <span className="muted">trained {new Date(model.trained_at).toLocaleString()} by {model.trained_by} on {model.trained_on} txns</span>
      </div>

      <div className="cards" style={{ marginTop: 12 }}>
        {['precision', 'recall', 'f1', 'roc_auc'].map((k) => {
          const v = m[k] ?? m[`${k}_vs_labels`]
          return (
            <div className="card" key={k}>
              <div className="label">{k.replace('_', '-')}{m[k] == null && m[`${k}_vs_labels`] != null ? ' (vs labels)' : ''}</div>
              <div className="value">{v != null ? Number(v).toFixed(3) : '—'}</div>
            </div>
          )
        })}
      </div>

      {cm && (
        <div>
          <h2>Confusion matrix {m.confusion_matrix ? '(held-out test set)' : '(vs available labels)'}</h2>
          <div className="cm-grid">
            <div className="cm-cell head"></div>
            <div className="cm-cell head">pred legit</div>
            <div className="cm-cell head">pred fraud</div>
            <div className="cm-cell head">true legit</div>
            <div className="cm-cell"><b>{cm[0][0]}</b><div className="muted">TN</div></div>
            <div className="cm-cell"><b>{cm[0][1]}</b><div className="muted">FP</div></div>
            <div className="cm-cell head">true fraud</div>
            <div className="cm-cell"><b>{cm[1][0]}</b><div className="muted">FN</div></div>
            <div className="cm-cell"><b>{cm[1][1]}</b><div className="muted">TP</div></div>
          </div>
        </div>
      )}

      {m.feature_importances && (
        <div style={{ marginTop: 14 }}>
          <h2>Top feature importances</h2>
          {Object.entries(m.feature_importances as Record<string, number>).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 6 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="mono">{k}</span><span>{(v * 100).toFixed(1)}%</span>
              </div>
              <div className="factor-bar"><div style={{ width: `${v * 100 * 2}%` }} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
