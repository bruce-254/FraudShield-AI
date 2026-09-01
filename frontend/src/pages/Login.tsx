import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Login() {
  const { user, signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await signIn(username, password)
    } catch {
      setError('Invalid username or password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-box" onSubmit={submit}>
        <h1>🛡 FraudShield AI</h1>
        <div className="subtitle">Defensive fraud detection &amp; transaction analytics</div>
        <div className="field">
          <label>Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && <div className="error">{error}</div>}
        <button disabled={busy || !username || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="hint">
          Development accounts (synthetic environment):<br />
          admin / AdminPass123! · analyst / AnalystPass123! · viewer / ViewerPass123!
        </div>
      </form>
    </div>
  )
}
