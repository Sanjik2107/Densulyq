import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login, verifyMfa, register } = useAuth()
  const [view, setView] = useState('login')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [mfaChallenge, setMfaChallenge] = useState('')
  const [mfaCode, setMfaCode] = useState('')

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [regName, setRegName] = useState('')
  const [regUsername, setRegUsername] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPhone, setRegPhone] = useState('')

  const handleLogin = async () => {
    const cleanUsername = username.trim()
    if (!cleanUsername || !password) { setError('Введите username и пароль.'); return }
    setLoading(true); setError(''); setInfo('')
    try {
      const data = await login(cleanUsername, password)
      if (data?.mfa_required) {
        setMfaChallenge(data.challenge_token)
        setInfo(data.dev_code ? `Dev 2FA code: ${data.dev_code}` : 'Введите 2FA-код.')
        setView('mfa')
      }
    }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleMfa = async () => {
    if (!mfaChallenge || !mfaCode.trim()) { setError('Введите 2FA-код.'); return }
    setLoading(true); setError('')
    try { await verifyMfa(mfaChallenge, mfaCode.trim()) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const handleRegister = async () => {
    const cleanName = regName.trim()
    const cleanUsername = regUsername.trim()
    if (!cleanName || !cleanUsername || !regPassword || !regConfirm) { setError('Заполните имя, username и пароль.'); return }
    if (regPassword !== regConfirm) { setError('Пароли не совпадают.'); return }
    if (regPassword.length < 6) { setError('Пароль должен содержать минимум 6 символов.'); return }
    setLoading(true); setError(''); setInfo('')
    try { await register({ name: cleanName, username: cleanUsername, password: regPassword, email: regEmail.trim() || null, phone: regPhone.trim() || null }) }
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
            {[['Patient demo','patient-demo','patient123'],['Doctor demo','doctor-demo','doctor123'],['Lab demo','lab-demo','lab123'],['Admin demo','admin-demo','admin123']].map(([title, u, p]) => (
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
            {isRegister ? 'Создайте patient account. Роли doctor, lab и admin создаются только через админку.' : 'Войдите по username и password. Роль будет определена автоматически.'}
          </p>
          {error && <div className="auth-error">{error}</div>}
          {info && <div className="auth-hint">{info}</div>}

          {view === 'mfa' ? (
            <>
              <div className="fg"><label>2FA code</label><input value={mfaCode} onChange={e=>setMfaCode(e.target.value)} placeholder="000000" inputMode="numeric" onKeyDown={e=>e.key==='Enter'&&handleMfa()}/></div>
              <div className="auth-actions">
                <button className="btn btn-primary" onClick={handleMfa} disabled={loading}>{loading ? 'Checking...' : 'Verify'}</button>
                <button className="btn btn-secondary" onClick={()=>{setView('login');setError('');setInfo('')}}>Back</button>
              </div>
            </>
          ) : isRegister ? (
            <>
              <div className="fg"><label>Full name</label><input value={regName} onChange={e=>setRegName(e.target.value)} placeholder="Your full name" autoComplete="name" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              <div className="fg"><label>Username</label><input value={regUsername} onChange={e=>setRegUsername(e.target.value)} placeholder="Create username" autoComplete="username" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              <div className="frow">
                <div className="fg"><label>Password</label><input type="password" value={regPassword} onChange={e=>setRegPassword(e.target.value)} placeholder="Create password" autoComplete="new-password" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
                <div className="fg"><label>Confirm password</label><input type="password" value={regConfirm} onChange={e=>setRegConfirm(e.target.value)} placeholder="Repeat password" autoComplete="new-password" onKeyDown={e=>e.key==='Enter'&&handleRegister()}/></div>
              </div>
              <div className="frow">
                <div className="fg"><label>Email</label><input type="email" value={regEmail} onChange={e=>setRegEmail(e.target.value)} placeholder="Optional email" autoComplete="email"/></div>
                <div className="fg"><label>Phone</label><input value={regPhone} onChange={e=>setRegPhone(e.target.value)} placeholder="Optional phone" autoComplete="tel"/></div>
              </div>
              <div className="auth-actions">
                <button className="btn btn-primary" onClick={handleRegister} disabled={loading}>{loading ? 'Creating...' : 'Create account'}</button>
                <button className="btn btn-secondary" onClick={()=>{setView('login');setError('')}}>Back to login</button>
              </div>
            </>
          ) : (
            <>
              <div className="fg"><label>Username</label><input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Enter username" autoComplete="username" onKeyDown={e=>e.key==='Enter'&&handleLogin()}/></div>
              <div className="fg"><label>Password</label><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter password" autoComplete="current-password" onKeyDown={e=>e.key==='Enter'&&handleLogin()}/></div>
              <div className="auth-actions">
                <button className="btn btn-primary" onClick={handleLogin} disabled={loading}>{loading ? 'Logging in...' : 'Login'}</button>
                <button className="btn btn-secondary" onClick={()=>{setView('register');setError('')}}>Register as patient</button>
              </div>
            </>
          )}
          <div className="auth-hint">
            {isRegister ? 'Регистрация создаёт аккаунт с ролью user и сразу открывает patient portal.' : 'После обычного логина user попадает в patient portal, doctor в doctor dashboard, lab в lab panel, admin в admin panel.'}
          </div>
        </div>
      </div>
    </div>
  )
}
