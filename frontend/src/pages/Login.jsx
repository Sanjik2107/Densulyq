import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'

export default function Login() {
  const { login, register } = useAuth()
  const toast = useToast()
  const [view, setView] = useState('login')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [regName, setRegName] = useState('')
  const [regUsername, setRegUsername] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPhone, setRegPhone] = useState('')

  const handleLogin = async () => {
    if (!username || !password) { setError('Введите username и пароль.'); return }
    setLoading(true); setError('')
    try { await login(username, password) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleRegister = async () => {
    if (!regName || !regUsername || !regPassword || !regConfirm) { setError('Заполните имя, username и пароль.'); return }
    if (regPassword !== regConfirm) { setError('Пароли не совпадают.'); return }
    if (regPassword.length < 6) { setError('Пароль должен содержать минимум 6 символов.'); return }
    setLoading(true); setError('')
    try { await register({ name: regName, username: regUsername, password: regPassword, email: regEmail || null, phone: regPhone || null }) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const isRegister = view === 'register'

  return (
    <div style={{ padding: 32, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="auth-shell">
        <div className="auth-panel">
          <div className="auth-badge">{isRegister ? 'Patient registration' : 'Unified access'}</div>
          <h1>Densaulyq Portal</h1>
          <p>Один логин для всех ролей. После входа система сама определяет, открыть patient portal, doctor dashboard или admin panel.</p>
          <div className="auth-points">
            {[['Patient demo','patient-demo','patient123'],['Doctor demo','doctor-demo','doctor123'],['Admin demo','admin-demo','admin123']].map(([title, u, p]) => (
              <div key={title} className="auth-point">
                <strong style={{ display:'block', marginBottom:6 }}>{title}</strong>
                <span>username: <code>{u}</code><br/>password: <code>{p}</code></span>
              </div>
            ))}
          </div>
        </div>
        <div className="auth-box">
          <h2 style={{ fontSize:24, letterSpacing:'-.6px' }}>{isRegister ? 'Register' : 'Login'}</h2>
          <p style={{ marginTop:8, color:'#64748b', fontSize:13.5 }}>
            {isRegister ? 'Создайте patient account. Роли doctor и admin создаются только через админку.' : 'Войдите по username и password. Роль будет определена автоматически.'}
          </p>
          {error && <div className="auth-error">{error}</div>}

          {isRegister ? (
            <>
              <div className="fg"><label>Full name</label><input value={regName} onChange={e=>setRegName(e.target.value)} placeholder="Your full name" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              <div className="fg"><label>Username</label><input value={regUsername} onChange={e=>setRegUsername(e.target.value)} placeholder="Create username" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              <div className="frow">
                <div className="fg"><label>Password</label><input type="password" value={regPassword} onChange={e=>setRegPassword(e.target.value)} placeholder="Create password" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
                <div className="fg"><label>Confirm password</label><input type="password" value={regConfirm} onChange={e=>setRegConfirm(e.target.value)} placeholder="Repeat password" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              </div>
              <div className="frow">
                <div className="fg"><label>Email</label><input type="email" value={regEmail} onChange={e=>setRegEmail(e.target.value)} placeholder="Optional email"/></div>
                <div className="fg"><label>Phone</label><input value={regPhone} onChange={e=>setRegPhone(e.target.value)} placeholder="Optional phone"/></div>
              </div>
              <div className="auth-actions">
                <button className="btn btn-primary" onClick={handleRegister} disabled={loading}>{loading ? 'Creating...' : 'Create account'}</button>
                <button className="btn btn-secondary" onClick={()=>{setView('login');setError('')}}>Back to login</button>
              </div>
            </>
          ) : (
            <>
              <div className="fg"><label>Username</label><input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter username" onKeyDown={e=>e.key==='Enter'&&handleLogin()}/></div>
              <div className="fg"><label>Password</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter password" onKeyDown={e=>e.key==='Enter'&&handleLogin()}/></div>
              <div className="auth-actions">
                <button className="btn btn-primary" onClick={handleLogin} disabled={loading}>{loading ? 'Logging in...' : 'Login'}</button>
                <button className="btn btn-secondary" onClick={()=>{setView('register');setError('')}}>Register as patient</button>
              </div>
            </>
          )}
          <div className="auth-hint">
            {isRegister ? 'Регистрация создаёт аккаунт с ролью user и сразу открывает patient portal.' : 'После обычного логина пользователь с ролью user попадает в patient portal, doctor в doctor dashboard, admin в admin panel.'}
          </div>
        </div>
      </div>
    </div>
  )
}
