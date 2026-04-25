import { useState, useEffect } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import Sidebar from './components/Sidebar.jsx'
import Login from './pages/Login.jsx'
import { Dashboard, Analyses, Appointments, Referrals, AIAssistant, Profile, AdminPanel } from './pages/Pages.jsx'
import { apiGet } from './api.js'
import { mapAnalysesList, mapAppointmentsList, mapReferralsList, mapUser } from './utils.jsx'

const PAGE_TITLES = {
  dashboard:'Dashboard', analyses:'Analysis results', referrals:'Referrals',
  appointments:'Appointments', ai:'AI Assistant', profile:'My profile',
  patients:'Patients', admin:'Admin panel',
}

export default function App() {
  const { user, isAuthenticated, isAdmin, isDoctor, isPatient, loading, logout, authState, updateStoredPage } = useAuth()
  const [page, setPage] = useState('dashboard')
  const [patientData, setPatientData] = useState({ analyses: [], appointments: [], referrals: [], doctors: [] })
  const [dataLoading, setDataLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    if (authState.page) setPage(authState.page)
  }, [authState.page])

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
    } catch {}
    setDataLoading(false)
  }

  const navigate = (id) => {
    setPage(id)
    updateStoredPage(id)
  }

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
    if (isDoctor && (page === 'dashboard' || page === 'patients')) return <button className="btn btn-secondary" onClick={loadPatientData}>Refresh patients</button>
    return null
  }

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return <Dashboard onNavigate={navigate} onOpenModal={() => setShowModal(true)} patientData={patientData} />
      case 'analyses': return <Analyses analyses={patientData.analyses} />
      case 'appointments': return <Appointments appointments={patientData.appointments} doctors={patientData.doctors} onRefresh={loadPatientData} showModal={showModal} onCloseModal={() => setShowModal(false)} />
      case 'referrals': return <Referrals referrals={patientData.referrals} />
      case 'ai': return <AIAssistant />
      case 'profile': return <Profile />
      case 'patients': return <Dashboard onNavigate={navigate} patientData={patientData} />
      case 'admin': return <AdminPanel />
      default: return <Dashboard onNavigate={navigate} onOpenModal={() => setShowModal(true)} patientData={patientData} />
    }
  }

  return (
    <div className="app">
      <Sidebar currentPage={page} onNavigate={navigate} onLogout={logout} />
      <main className="main">
        <header className="topbar">
          <h1>{title}</h1>
          <div>{getTopbarActions()}</div>
        </header>
        <div className="content">
          {renderPage()}
        </div>
      </main>
    </div>
  )
}
