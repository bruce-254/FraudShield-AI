import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth'
import Layout from './components/Layout'
import Alerts from './pages/Alerts'
import Cases from './pages/Cases'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import MLModels from './pages/MLModels'
import Reports from './pages/Reports'
import Rules from './pages/Rules'
import Transactions from './pages/Transactions'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/rules" element={<Rules />} />
            <Route path="/ml" element={<MLModels />} />
            <Route path="/reports" element={<Reports />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
