import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../auth'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/cases', label: 'Cases' },
  { to: '/rules', label: 'Rules' },
  { to: '/ml', label: 'ML Models' },
  { to: '/reports', label: 'Reports' },
]

export default function Layout() {
  const { user, loading, signOut } = useAuth()
  if (loading) return <div className="login-wrap">Loading…</div>
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">🛡 Fraud<span>Shield</span> AI</div>
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'}
            className={({ isActive }) => `navlink${isActive ? ' active' : ''}`}>
            {l.label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div className="userbox">
          <b>{user.full_name || user.username}</b>
          role: {user.role}
          <div style={{ marginTop: 8 }}>
            <button className="secondary small" onClick={signOut}>Sign out</button>
          </div>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
