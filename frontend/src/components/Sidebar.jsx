import { useAuth } from '../context/AuthContext.jsx'
import { formatRole } from '../utils.jsx'

const USER_PAGES = [
  { id:'dashboard', label:'Dashboard', group:'Overview', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg> },
  { id:'analyses', label:'My analyses', group:'Medical records', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V8l-5-5z"/><polyline points="14 3 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg> },
  { id:'referrals', label:'Referrals', group:'Medical records', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> },
  { id:'appointments', label:'Appointments', group:'Visits', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> },
  { id:'ai', label:'AI Assistant', group:'AI', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> },
  { id:'profile', label:'My profile', group:'Account', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> },
]

const ADMIN_PAGES = [
  { id:'dashboard', label:'Dashboard', group:'Overview', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg> },
  { id:'admin', label:'Admin panel', group:'Management', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M12 4h9"/><path d="M4 9h16"/><path d="M4 15h16"/><path d="M6 4v16"/></svg> },
  { id:'profile', label:'My profile', group:'Account', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> },
]

const DOCTOR_PAGES = [
  { id:'dashboard', label:'Dashboard', group:'Overview', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg> },
  { id:'patients', label:'Patients', group:'Clinical', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg> },
  { id:'profile', label:'My profile', group:'Account', icon:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> },
]

export default function Sidebar({ currentPage, onNavigate, onLogout }) {
  const { user, isAdmin, isDoctor } = useAuth()
  if (!user) return null

  const pages = isAdmin ? ADMIN_PAGES : isDoctor ? DOCTOR_PAGES : USER_PAGES
  const groups = [...new Set(pages.map(p => p.group))]

  return (
    <aside className="sidebar">
      <div className="logo">
        <h2>Den<span>saulyq</span></h2>
        <p>Patient, doctor &amp; admin portal</p>
      </div>
      <nav className="nav">
        {groups.map(group => (
          <div key={group} className="nav-group">
            <div className="nav-group-label">{group}</div>
            {pages.filter(p => p.group === group).map(page => (
              <div
                key={page.id}
                className={`nav-item${currentPage === page.id ? ' active' : ''}`}
                onClick={() => onNavigate(page.id)}
              >
                {page.icon} {page.label}
              </div>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-user">
        <div className="sidebar-user-main">
          <div className="avatar">{user.initials || 'PT'}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: '#fff', fontWeight: 500 }}>{user.name}</div>
            <div style={{ fontSize: 11, color: '#64748b' }}>
              {formatRole(user.role)}{user.department ? ' · ' + user.department : ''}
            </div>
          </div>
        </div>
        <button className="sidebar-switch" onClick={onLogout}>Logout</button>
      </div>
    </aside>
  )
}
