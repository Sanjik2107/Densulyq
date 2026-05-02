import { useState, useEffect } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import { useToast } from './context/ToastContext.jsx'
import Sidebar from './components/Sidebar.jsx'
import Login from './pages/Login.jsx'
import { Dashboard, Analyses, Appointments, Referrals, AIAssistant, Profile, AdminPanel } from './pages/Pages.jsx'
import { apiGet } from './api.js'
import { mapAnalysesList, mapAppointmentsList, mapReferralsList } from './utils.jsx'

const PAGE_TITLES = {
  dashboard:'Dashboard', analyses:'Analysis results', referrals:'Referrals',
  appointments:'Appointments', ai:'AI Assistant', profile:'My profile',
  patients:'Patients', admin:'Admin panel',
}

export default function App() {
  const toast = useToast()
  const { user, isAuthenticated, isAdmin, isDoctor, isPatient, loading, logout, authState, updateStoredPage } = useAuth()
  const [page, setPage] = useState('dashboard')
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('densaulyq-theme') || 'light' } catch { return 'light' }
  })
  const [patientData, setPatientData] = useState({ analyses: [], appointments: [], referrals: [], doctors: [] })
  const [dataLoading, setDataLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [doctorRefresh, setDoctorRefresh] = useState(() => async () => {})

  useEffect(() => {
    if (authState.page) setPage(authState.page)
  }, [authState.page])

  useEffect(() => {
    document.body.dataset.theme = theme
    try { localStorage.setItem('densaulyq-theme', theme) } catch {}
  }, [theme])

  useEffect(() => {
    if (!isAuthenticated || !user) return
    if (isPatient) loadPatientData()
  }, [isAuthenticated, user?.id])

  const loadPatientData = async () => {
    setDataLoading(true)
    try {
      const [u, an, ap, rf, dr] = await Promise.all([
        apiGet('/user/' + user.id),
        apiGet('/analyses/' + user.id),
        apiGet('/appointments/' + user.id),
        apiGet('/referrals/' + user.id),
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
    } finally {
      setDataLoading(false)
    }
  }

  const navigate = (id) => {
    setPage(id)
    updateStoredPage(id)
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

  const title = PAGE_TITLES[page] || 'Dashboard'

  const getTopbarActions = () => {
    if (isPatient && page === 'appointments') return <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Book appointment</button>
    if (isPatient && page === 'dashboard') return <button className="btn btn-primary" onClick={() => navigate('ai')}>Ask AI</button>
    if (isAdmin && page === 'admin') return <button className="btn btn-primary" onClick={() => document.getElementById('new-user-form')?.scrollIntoView({ behavior: 'smooth' })}>+ New user</button>
    if (isDoctor && (page === 'dashboard' || page === 'patients')) return <button className="btn btn-secondary" onClick={() => doctorRefresh()}>Refresh patients</button>
    return null
  }

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return <Dashboard onNavigate={navigate} onOpenModal={openAppointmentModal} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'analyses': return <Analyses analyses={patientData.analyses} />
      case 'appointments': return <Appointments appointments={patientData.appointments} doctors={patientData.doctors} onRefresh={loadPatientData} showModal={showModal} onCloseModal={() => setShowModal(false)} onOpenModal={() => setShowModal(true)} />
      case 'referrals': return <Referrals referrals={patientData.referrals} />
      case 'ai': return <AIAssistant />
      case 'profile': return <Profile />
      case 'patients': return <Dashboard onNavigate={navigate} patientData={patientData} onDoctorRefreshReady={setDoctorRefresh} />
      case 'admin': return <AdminPanel />
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
