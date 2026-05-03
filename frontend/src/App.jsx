import { useState, useEffect, useCallback } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import { useToast } from './context/ToastContext.jsx'
import { useI18n } from './context/I18nContext.jsx'
import Sidebar from './components/Sidebar.jsx'
import Login from './pages/Login.jsx'
import { Dashboard, Analyses, Appointments, Referrals, AIAssistant, Profile, AdminPanel, LabPanel } from './pages/Pages.jsx'
import { apiGet } from './api.js'
import { mapAnalysesList, mapAppointmentsList, mapReferralsList } from './utils.jsx'

const PAGES_BY_ROLE = {
  admin: ['dashboard', 'admin', 'profile'],
  lab: ['dashboard', 'lab', 'profile'],
  doctor: ['dashboard', 'patients', 'profile'],
  user: ['dashboard', 'analyses', 'referrals', 'appointments', 'ai', 'profile'],
}

const DEFAULT_PAGE_BY_ROLE = {
  admin: 'admin',
  lab: 'lab',
  doctor: 'dashboard',
  user: 'dashboard',
}

function pageForRole(requestedPage, role) {
  const safeRole = role || 'user'
  const allowed = PAGES_BY_ROLE[safeRole] || PAGES_BY_ROLE.user
  return allowed.includes(requestedPage) ? requestedPage : (DEFAULT_PAGE_BY_ROLE[safeRole] || 'dashboard')
}

export default function App() {
  const toast = useToast()
  const { lang, setLang, tr } = useI18n()
  const { user, isAuthenticated, isAdmin, isLab, isDoctor, isPatient, loading, logout, authState, updateStoredPage } = useAuth()
  const [page, setPage] = useState('dashboard')
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('densaulyq-theme') || 'light' } catch { return 'light' }
  })
  const [patientData, setPatientData] = useState({ analyses: [], appointments: [], referrals: [], doctors: [] })
  const [showModal, setShowModal] = useState(false)
  const [doctorRefresh, setDoctorRefresh] = useState(() => async () => {})
  const userId = user?.id

  const loadPatientData = useCallback(async () => {
    if (!userId) return
    try {
      const [, an, ap, rf, dr] = await Promise.all([
        apiGet('/user/' + userId),
        apiGet('/analyses/' + userId),
        apiGet('/appointments/' + userId),
        apiGet('/referrals/' + userId),
        apiGet('/doctors'),
      ])
      setPatientData({
        analyses: mapAnalysesList(an),
        appointments: mapAppointmentsList(ap),
        referrals: mapReferralsList(rf),
        doctors: (dr.doctors || []),
      })
    } catch (e) {
      toast(e.message || 'Failed to load patient data.')
    }
  }, [toast, userId])

  useEffect(() => {
    if (!authState.page || !user?.role) return
    const safePage = pageForRole(authState.page, user.role)
    setPage(safePage)
    if (safePage !== authState.page) updateStoredPage(safePage)
  }, [authState.page, updateStoredPage, user?.role])

  useEffect(() => {
    document.body.dataset.theme = theme
    try { localStorage.setItem('densaulyq-theme', theme) } catch { return }
  }, [theme])

  useEffect(() => {
    if (!isAuthenticated || !user) return
    if (isPatient) loadPatientData()
  }, [isAuthenticated, isPatient, loadPatientData, user])

  const navigate = (id) => {
    const safePage = pageForRole(id, user?.role)
    setPage(safePage)
    updateStoredPage(safePage)
  }

  const openAppointmentModal = () => {
    navigate('appointments')
    setShowModal(true)
  }

  const toggleTheme = () => setTheme(current => current === 'dark' ? 'light' : 'dark')

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
      <p>Loading portal...</p>
    </div>
  )

  if (!isAuthenticated) return <Login />

  const title = tr(page) || 'Dashboard'

  const getTopbarActions = () => {
    if (isPatient && page === 'appointments') return <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Book appointment</button>
    if (isPatient && page === 'dashboard') return <button className="btn btn-primary" onClick={() => navigate('ai')}>Ask AI</button>
    if (isAdmin && page === 'admin') return <button className="btn btn-primary" onClick={() => document.getElementById('new-user-form')?.scrollIntoView({ behavior: 'smooth' })}>{tr('newUser')}</button>
    if (isDoctor && (page === 'dashboard' || page === 'patients')) return <button className="btn btn-secondary" onClick={() => doctorRefresh()}>{tr('refreshPatients')}</button>
    return null
  }

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return isLab ? <LabPanel /> : <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'analyses': return <Analyses analyses={patientData.analyses} />
      case 'appointments': return isPatient ? <Appointments appointments={patientData.appointments} doctors={patientData.doctors} onRefresh={loadPatientData} showModal={showModal} onCloseModal={() => setShowModal(false)} onOpenModal={() => setShowModal(true)} /> : <Dashboard onNavigate={navigate} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'referrals': return <Referrals referrals={patientData.referrals} />
      case 'ai': return <AIAssistant />
      case 'profile': return <Profile />
      case 'patients': return isDoctor ? <Dashboard onNavigate={navigate} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} /> : <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'admin': return isAdmin ? <AdminPanel /> : <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'lab': return isLab ? <LabPanel /> : <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      default: return <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
    }
  }

  return (
    <div className="app">
      <Sidebar currentPage={page} onNavigate={navigate} onLogout={logout} />
      <main className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <div className="topbar-actions">
            <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">{theme === 'dark' ? 'Light' : 'Dark'}</button>
            <select className="theme-toggle" value={lang} onChange={e=>setLang(e.target.value)} title="Language">
              <option value="en">EN</option>
              <option value="ru">RU</option>
              <option value="kz">KZ</option>
            </select>
            {getTopbarActions()}
          </div>
        </header>
        <div className="content">
          {renderPage()}
        </div>
      </main>
    </div>
  )
}
