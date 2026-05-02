import { useState, useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { apiGet, apiPatch, apiPost, apiPut } from '../api.js'
import {
  badgeForStatus, getRoleChip, formatRole, mapAnalysesList, mapAppointmentsList,
  mapReferralsList, mapUser, formatAnalysisResultsText, parseAnalysisResultsText,
  getLocalDateIso, getDefaultBookingDate, ANALYSIS_NAME_OPTIONS,
} from '../utils.jsx'

// ── PATIENT DASHBOARD ──
function PatientDashboard({ analyses, appointments, referrals, onNavigate, onOpenModal }) {
  const { user } = useAuth()
  const score = (() => {
    const total = analyses.reduce((s,a) => s+(a.results||[]).length, 0)
    if (!total) return 82
    const bad = analyses.reduce((s,a) => s+(a.results||[]).filter(r=>r.ok===false).length, 0)
    return Math.max(55, 92 - Math.round((bad/total)*40))
  })()
  const readyAnalyses = analyses.filter(a=>['ready','reviewed'].includes(a.status)).length
  const nextAppt = appointments[0]
  const activeRefs = referrals.filter(r=>r.status==='active').length
  const pendingAnalyses = analyses.filter(a=>['ordered','processing'].includes(a.status)).length
  const abnormalCount = analyses.reduce((s,a)=>s+(a.results||[]).filter(r=>r.ok===false).length,0)
  const latestRef = referrals[0]
  const careStage = nextAppt
    ? `Next visit with ${nextAppt.doctor} on ${nextAppt.day} ${nextAppt.mon} at ${nextAppt.time}.`
    : pendingAnalyses ? `${pendingAnalyses} analysis${pendingAnalyses>1?'es are':' is'} still in progress.`
    : 'No urgent activity right now. You can schedule a preventive visit.'
  const scoreBadge = score>=85?'b-green':score>=70?'b-warn':'b-red'
  const scoreStatus = score>=85?'Excellent':score>=70?'Good':'Needs attention'
  const r=42, circ=2*Math.PI*r, arc=circ*score/100

  return (
    <div className="page">
      <div className="hero-card" style={{marginBottom:18}}>
        <div className="hero-grid">
          <div>
            <div className="hero-eyebrow">Personal care cockpit</div>
            <div className="hero-title">Good to see you, {user?.name?.split(' ')[0]||'Patient'}.</div>
            <div className="hero-copy">{careStage} {abnormalCount?'Your latest records still have a few signals worth tracking.':'Your recent records look stable, so this is a good moment to stay proactive.'}</div>
            <div className="hero-actions">
              <button className="btn btn-hero-primary" onClick={onOpenModal}>Book a visit</button>
              <button className="btn btn-hero-ghost" onClick={()=>onNavigate('analyses')}>Open analyses</button>
              <button className="btn btn-hero-ghost" onClick={()=>onNavigate('ai')}>Ask AI assistant</button>
            </div>
          </div>
          <div className="hero-panel">
            <div className="hero-panel-title">Today at a glance</div>
            {[['Health score',score+'/100'],['Ready analyses',readyAnalyses],['Abnormal markers',abnormalCount],['Active referrals',activeRefs],['Next appointment',nextAppt?`${nextAppt.day} ${nextAppt.mon} · ${nextAppt.time}`:'Not scheduled']].map(([l,v])=>(
              <div key={l} className="hero-metric"><div className="hero-metric-label">{l}</div><div className="hero-metric-value">{v}</div></div>
            ))}
          </div>
        </div>
      </div>
      <div className="insight-grid">
        <div className="insight-card">
          <div className="insight-kicker">Current balance</div>
          <div style={{display:'flex',alignItems:'center',gap:18}}>
            <div className="hcircle">
              <svg width="96" height="96" viewBox="0 0 96 96">
                <circle cx="48" cy="48" r={r} fill="none" stroke="#e2e8f0" strokeWidth="8"/>
                <circle cx="48" cy="48" r={r} fill="none" stroke="#2563eb" strokeWidth="8" strokeDasharray={`${arc} ${circ}`} strokeLinecap="round"/>
              </svg>
              <div className="hcircle-txt"><div className="hcircle-num">{score}</div><div className="hcircle-lbl">of 100</div></div>
            </div>
            <div>
              <span className={`badge ${scoreBadge}`} style={{marginBottom:10}}>{scoreStatus}</span>
              <div className="insight-copy">{abnormalCount?'A few lab markers need attention, but the overall picture is still manageable.':'No strong warning signals in the latest results.'}</div>
            </div>
          </div>
        </div>
        <div className="insight-card">
          <div className="insight-kicker">Next best step</div>
          <div className="insight-title">{nextAppt?'Prepare for your visit':'Stay proactive'}</div>
          <div className="insight-copy">{nextAppt?`Your next visit is with ${nextAppt.doctor}. Keep notes about symptoms and bring recent questions.`:'If something feels off, book a visit. If not, use this calm period for preventive checks and profile updates.'}</div>
        </div>
        <div className="insight-card">
          <div className="insight-kicker">Signals to watch</div>
          <div className="signal-list">
            {[{label:`${readyAnalyses} ready analyses available`,tone:'#2563eb'},{label:`${pendingAnalyses} items still in workflow`,tone:'#f59e0b'},{label:activeRefs?`${activeRefs} active referrals before ${latestRef?latestRef.deadline:'their deadlines'}`:'No open referrals right now',tone:'#10b981'}].map(item=>(
              <div key={item.label} className="signal-item"><div className="signal-dot" style={{background:item.tone}}/><div style={{fontSize:13,lineHeight:1.55,color:'#334155'}}>{item.label}</div></div>
            ))}
          </div>
        </div>
      </div>
      <div className="section-split">
        <div className="card">
          <div className="card-head"><div><h3>Latest analyses</h3><p>Most recent lab updates and result states</p></div><button className="btn btn-secondary btn-sm" onClick={()=>onNavigate('analyses')}>All →</button></div>
          <div className="card-body" style={{paddingTop:8}}>
            {analyses.length ? analyses.slice(0,3).map(item=>(
              <div key={item.id} className="li">
                <div className="li-icon" style={{background:'#dbeafe',color:'#2563eb',fontSize:12,fontWeight:700}}>LAB</div>
                <div style={{flex:1}}><div style={{fontSize:13.5,fontWeight:500}}>{item.name}</div><div style={{fontSize:12,color:'#64748b'}}>{item.date} · {item.doctor}</div>{(item.labNote||item.doctorNote)&&<div style={{fontSize:12,color:'#475569',marginTop:4}}>{item.labNote||item.doctorNote}</div>}</div>
                <span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span>
              </div>
            )) : <div className="empty">No analyses linked to this user yet.</div>}
          </div>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:18}}>
          <div className="card">
            <div className="card-head"><div><h3>Upcoming appointments</h3><p>Your nearest visits and their status</p></div><button className="btn btn-secondary btn-sm" onClick={()=>onNavigate('appointments')}>All →</button></div>
            <div className="card-body" style={{paddingTop:10}}>
              {appointments.length ? appointments.slice(0,3).map(item=>(
                <div key={item.id} className="appt">
                  <div className="appt-date"><div className="appt-day">{item.day}</div><div className="appt-mon">{item.mon}</div></div>
                  <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600}}>{item.doctor}</div><div style={{fontSize:12,color:'#64748b'}}>{item.spec} · {item.place}</div></div>
                  <div style={{textAlign:'right'}}><div style={{fontSize:14,fontWeight:600}}>{item.time}</div><span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span></div>
                </div>
              )) : <div className="empty">No appointments yet.</div>}
            </div>
          </div>
          <div className="card">
            <div className="card-head"><div><h3>Active referrals</h3><p>Directions and follow-up items</p></div><button className="btn btn-secondary btn-sm" onClick={()=>onNavigate('referrals')}>All →</button></div>
            <div className="card-body" style={{paddingTop:8}}>
              {referrals.length ? referrals.map(item=>(
                <div key={item.id} className="li">
                  <div className="li-icon" style={{background:item.status==='active'?'#d1fae5':'#f1f5f9',color:item.status==='active'?'#059669':'#64748b',fontSize:12,fontWeight:700}}>REF</div>
                  <div style={{flex:1}}><div style={{fontSize:13.5,fontWeight:500}}>{item.name}</div><div style={{fontSize:12,color:'#64748b'}}>from {item.from} · until {item.deadline}</div></div>
                  <span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span>
                </div>
              )) : <div className="empty">No referrals linked to this user.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── DOCTOR DASHBOARD ──
function DoctorDashboard({ onNavigate, onDoctorRefreshReady }) {
  const { user } = useAuth()
  const [patients, setPatients] = useState([])
  const [stats, setStats] = useState({})
  const [activePatient, setActivePatient] = useState(null)
  const [activeAnalyses, setActiveAnalyses] = useState([])
  const [activeAppts, setActiveAppts] = useState([])
  const [activeRefs, setActiveRefs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 12
  const toast = useToast()

  const loadPatients = async (nextOffset = offset) => {
    setLoading(true)
    setError('')
    try {
      const d = await apiGet('/doctor/patients', { limit, offset: nextOffset })
      const pts = (d.patients || []).map(p => ({ ...mapUser(p), ready_analyses: p.ready_analyses || 0, appointment_count: p.appointment_count || 0, active_referrals: p.active_referrals || 0, latest_analysis_date: p.latest_analysis_date || null, next_appointment: p.next_appointment || null }))
      setPatients(pts)
      setStats(d.stats || {})
      setOffset(nextOffset)
      if (!activePatient && pts.length) selectPatient(pts[0])
    } catch (e) {
      setError(e.message || 'Failed to load patients')
      toast(e.message || 'Failed to load patients')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadPatients(0) }, [])
  useEffect(() => {
    if (!onDoctorRefreshReady) return
    onDoctorRefreshReady(() => () => loadPatients(offset))
  }, [onDoctorRefreshReady, offset])

  const selectPatient = async (p) => {
    setActivePatient(p)
    try {
      const [an, ap, rf] = await Promise.all([apiGet('/analyses/' + p.id), apiGet('/appointments/' + p.id), apiGet('/referrals/' + p.id)])
      setActiveAnalyses(mapAnalysesList(an))
      setActiveAppts(mapAppointmentsList(ap))
      setActiveRefs(mapReferralsList(rf))
    } catch (e) {
      toast(e.message || 'Failed to load patient details')
    }
  }

  const [showAssign, setShowAssign] = useState(false)
  const [anName, setAnName] = useState(''), [anDate, setAnDate] = useState(''), [anNote, setAnNote] = useState('')
  const [showReview, setShowReview] = useState(false)
  const [reviewId, setReviewId] = useState(null), [reviewNote, setReviewNote] = useState('')
  const [showBook, setShowBook] = useState(false)
  const [bookDate, setBookDate] = useState(getDefaultBookingDate())
  const [bookSlots, setBookSlots] = useState([])
  const [bookSlot, setBookSlot] = useState('')
  const [bookReason, setBookReason] = useState('')
  const [bookLoading, setBookLoading] = useState(false)

  const assignAnalysis = async () => {
    if (!anName.trim()) return toast('Enter analysis name.')
    try {
      await apiPost(`/doctor/patients/${activePatient.id}/analyses`, {name:anName, scheduled_for:anDate||undefined, doctor_note:anNote||undefined})
      toast('Analysis assigned.','success'); setShowAssign(false)
      const an = await apiGet('/analyses/'+activePatient.id); setActiveAnalyses(mapAnalysesList(an))
    } catch(e) { toast(e.message) }
  }

  const submitReview = async () => {
    try {
      await apiPut(`/doctor/analyses/${reviewId}/review`, {doctor_note:reviewNote||null})
      toast('Review saved.','success'); setShowReview(false)
      const an = await apiGet('/analyses/'+activePatient.id); setActiveAnalyses(mapAnalysesList(an))
    } catch(e) { toast(e.message) }
  }

  const loadDoctorSlots = async (dt = bookDate) => {
    if (!user?.id || !dt) return
    setBookLoading(true); setBookSlot(''); setBookSlots([])
    try {
      const data = await apiGet(`/doctors/${user.id}/availability`, { date: dt })
      setBookSlots(data.available_slots || [])
    } catch (e) {
      toast(e.message || 'Failed to load available slots')
    } finally {
      setBookLoading(false)
    }
  }

  const openBookVisit = () => {
    const nextDate = getDefaultBookingDate()
    setBookDate(nextDate)
    setBookReason('')
    setShowBook(true)
    loadDoctorSlots(nextDate)
  }

  const submitBookVisit = async () => {
    if (!activePatient) return toast('Select a patient first.')
    if (!bookSlot) return toast('Select date and time.')
    try {
      await apiPost('/appointments', {
        user_id: activePatient.id,
        doctor_user_id: user.id,
        date: bookDate,
        time: bookSlot,
        reason: bookReason,
      })
      toast('Visit booked.', 'success')
      setShowBook(false)
      const ap = await apiGet('/appointments/' + activePatient.id)
      setActiveAppts(mapAppointmentsList(ap))
      loadPatients(offset)
    } catch (e) {
      toast(e.message || 'Failed to book visit')
    }
  }

  return (
    <div className="page">
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:16,marginBottom:18}}>
        {[{lbl:'Patients',val:stats.total_patients||0,sub:'Visible patient accounts',ico:'PTS',bg:'#ede9fe',c:'#7c3aed'},{lbl:'Ready analyses',val:stats.ready_analyses||0,sub:'Completed lab results',ico:'LAB',bg:'#dbeafe',c:'#2563eb'},{lbl:'Appointments',val:stats.appointments||0,sub:'Scheduled visits',ico:'APT',bg:'#fef3c7',c:'#d97706'},{lbl:'Active referrals',val:stats.active_referrals||0,sub:'Open clinical directions',ico:'REF',bg:'#d1fae5',c:'#059669'}].map(card=>(
          <div key={card.lbl} className="stat">
            <div className="stat-icon" style={{background:card.bg,color:card.c,fontSize:12,fontWeight:700}}>{card.ico}</div>
            <div className="stat-lbl">{card.lbl}</div>
            <div className="stat-val" style={{color:card.c}}>{card.val}</div>
            <div className="stat-sub">{card.sub}</div>
          </div>
        ))}
      </div>
      <div className="admin-layout">
        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h3>Patients in focus</h3><p>Quick access to available patient accounts</p></div><button className="btn btn-secondary btn-sm" onClick={()=>loadPatients(offset)}>Refresh</button></div>
            <div className="card-body" style={{padding:0}}>
              <table className="tbl">
                <thead><tr><th>Name</th><th>Last analysis</th><th>Appointments</th><th>Ready</th></tr></thead>
                <tbody>
                  {patients.length ? patients.slice(0,5).map(p=>(
                    <tr key={p.id} onClick={()=>selectPatient(p)} className={activePatient?.id===p.id?'active-row':''} style={{cursor:'pointer'}}>
                      <td style={{fontWeight:500}}>{p.name}</td>
                      <td style={{color:'#64748b'}}>{p.latest_analysis_date||'—'}</td>
                      <td style={{color:'#64748b'}}>{p.appointment_count||0}</td>
                      <td><span className="badge b-blue">{p.ready_analyses||0}</span></td>
                    </tr>
                  )) : <tr><td colSpan="4"><div className="empty">{loading ? 'Loading patients...' : (error || 'No patient records available.')}</div></td></tr>}
                </tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => loadPatients(Math.max(0, offset - limit))} disabled={offset === 0 || loading}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => loadPatients(offset + limit)} disabled={patients.length < limit || loading}>Next</button>
              </div>
            </div>
          </div>
        </div>
        {activePatient && (
          <div className="stack">
            <div className="card">
              <div style={{padding:22,display:'flex',alignItems:'center',gap:18,borderBottom:'1px solid #e2e8f0'}}>
                <div style={{width:62,height:62,borderRadius:'50%',background:'#8b5cf6',display:'flex',alignItems:'center',justifyContent:'center',fontSize:18,fontWeight:700,color:'#fff'}}>{activePatient.initials}</div>
                <div><h2 style={{fontSize:18,marginBottom:6}}>{activePatient.name}</h2><div className="inline-badges"><span className="badge b-blue">Username: {activePatient.username||'—'}</span>{getRoleChip(activePatient.role)}</div></div>
              </div>
              <div className="card-body">
                {[['Phone',activePatient.phone||'—'],['Email',activePatient.email||'—'],['Blood type',activePatient.blood||'—']].map(([k,v])=>(
                  <div key={k} className="kv"><span style={{fontSize:13,color:'#64748b'}}>{k}</span><span style={{fontSize:13,fontWeight:500}}>{v}</span></div>
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-head"><div><h3>Recent analyses</h3></div><button className="btn btn-secondary btn-sm" onClick={()=>setShowAssign(true)}>Assign analysis</button></div>
              <div className="card-body" style={{paddingTop:10}}>
                {activeAnalyses.slice(0,4).map(item=>(
                  <div key={item.id} className="li">
                    <div className="li-icon" style={{background:'#ede9fe'}}>🧪</div>
                    <div style={{flex:1}}><div style={{fontSize:13.5,fontWeight:500}}>{item.name}</div><div style={{fontSize:12,color:'#64748b'}}>{item.date} · {item.doctor}</div></div>
                    <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:6}}>
                      <span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span>
                      {(item.status==='ready'||item.status==='reviewed')&&item.status!=='reviewed'&&<button className="btn btn-secondary btn-sm" onClick={()=>{setReviewId(item.id);setReviewNote(item.doctorNote||'');setShowReview(true)}}>Doctor review</button>}
                    </div>
                  </div>
                ))}
                {!activeAnalyses.length&&<div className="empty">No analyses found.</div>}
              </div>
            </div>
            <div className="card">
              <div className="card-head">
                <div><h3>Appointments</h3><p>Visits scheduled for this patient</p></div>
                <button className="btn btn-primary btn-sm" onClick={openBookVisit}>Book visit</button>
              </div>
              <div className="card-body" style={{padding:0}}>
                <table className="tbl">
                  <thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Status</th></tr></thead>
                  <tbody>
                    {activeAppts.length ? activeAppts.map(ap => (
                      <tr key={ap.id}>
                        <td style={{color:'#64748b'}}>{ap.dateISO || '—'}</td>
                        <td style={{fontWeight:600}}>{ap.time || '—'}</td>
                        <td style={{fontWeight:500}}>{ap.doctor || '—'}</td>
                        <td><span className={`badge ${badgeForStatus(ap.status)}`}>{ap.status}</span></td>
                      </tr>
                    )) : <tr><td colSpan="4"><div className="empty">No appointments found.</div></td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
      {showAssign&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Assign analysis</h3><button className="modal-close" onClick={()=>setShowAssign(false)}>✕</button></div><div className="modal-bd"><div className="fg"><label>Analysis name</label><input list="an-opts" value={anName} onChange={e=>setAnName(e.target.value)} placeholder="Choose or type"/><datalist id="an-opts">{ANALYSIS_NAME_OPTIONS.map(n=><option key={n} value={n}/>)}</datalist></div><div className="fg"><label>Scheduled date</label><input type="date" value={anDate} min={getLocalDateIso(0)} onChange={e=>setAnDate(e.target.value)}/></div><div className="fg"><label>Doctor note</label><textarea value={anNote} onChange={e=>setAnNote(e.target.value)} placeholder="Preparation instructions..."/></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setShowAssign(false)}>Cancel</button><button className="btn btn-primary" onClick={assignAnalysis}>Assign</button></div></div></div>}
      {showReview&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Doctor review</h3><button className="modal-close" onClick={()=>setShowReview(false)}>✕</button></div><div className="modal-bd"><div className="fg"><label>Doctor note</label><textarea value={reviewNote} onChange={e=>setReviewNote(e.target.value)} placeholder="Clinical interpretation..."/></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setShowReview(false)}>Cancel</button><button className="btn btn-primary" onClick={submitReview}>Save review</button></div></div></div>}
      {showBook&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Book visit</h3><button className="modal-close" onClick={()=>setShowBook(false)}>✕</button></div><div className="modal-bd"><div className="fg"><label>Patient</label><input value={activePatient?.name||''} disabled /></div><div className="frow"><div className="fg"><label>Date</label><input type="date" value={bookDate} min={getLocalDateIso(0)} onChange={e=>{setBookDate(e.target.value);loadDoctorSlots(e.target.value)}}/></div><div className="fg"><label>Session time</label><select value={bookSlot} onChange={e=>setBookSlot(e.target.value)} disabled={bookLoading||!bookSlots.length}><option value="">{bookLoading?'Loading...':!bookSlots.length?'No free slots':'Select time slot'}</option>{bookSlots.map(s=><option key={s} value={s}>{s}</option>)}</select></div></div><div className="fg"><label>Reason</label><textarea value={bookReason} onChange={e=>setBookReason(e.target.value)} placeholder="Visit reason..."/></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setShowBook(false)}>Cancel</button><button className="btn btn-primary" onClick={submitBookVisit}>Book</button></div></div></div>}
    </div>
  )
}

// ── ADMIN DASHBOARD ──
function AdminDashboard({ onNavigate }) {
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState({})
  const [analyses, setAnalyses] = useState([])
  const [rbac, setRbac] = useState([])

  useEffect(() => {
    Promise.all([apiGet('/admin/users'), apiGet('/admin/analyses'), apiGet('/rbac/model')]).then(([u,a,r])=>{
      setUsers((u.users||[]).map(mapUser)); setStats(u.stats||{}); setAnalyses(mapAnalysesList(a.analyses||[])); setRbac(r.roles||[])
    })
  }, [])

  const adminRole = rbac.find(r=>r.role==='admin')
  const adminPerms = adminRole?.permissions||[]

  return (
    <div className="page">
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:16,marginBottom:18}}>
        {[{lbl:'Total users',val:stats.total_users||0,sub:'All accounts in SQLite',ico:'ALL',bg:'#dbeafe',c:'#2563eb'},{lbl:'Admins',val:stats.admins||0,sub:'Privileged accounts',ico:'ADM',bg:'#ede9fe',c:'#7c3aed'},{lbl:'Doctors',val:stats.doctors||0,sub:'Clinical staff accounts',ico:'DOC',bg:'#f3e8ff',c:'#9333ea'},{lbl:'Patients',val:stats.users||0,sub:'Standard portal accounts',ico:'USR',bg:'#d1fae5',c:'#059669'},{lbl:'Active',val:stats.active_users||0,sub:'Accounts with access',ico:'ON',bg:'#fef3c7',c:'#d97706'}].map(card=>(
          <div key={card.lbl} className="stat"><div className="stat-icon" style={{background:card.bg,color:card.c,fontSize:12,fontWeight:700}}>{card.ico}</div><div className="stat-lbl">{card.lbl}</div><div className="stat-val" style={{color:card.c}}>{card.val}</div><div className="stat-sub">{card.sub}</div></div>
        ))}
      </div>
      <div className="admin-layout">
        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h3>Recent accounts</h3><p>Users available in the database</p></div><button className="btn btn-secondary btn-sm" onClick={()=>onNavigate('admin')}>Open panel →</button></div>
            <div className="card-body" style={{padding:0}}>
              <table className="tbl"><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th></tr></thead>
                <tbody>{users.slice(0,6).map(u=>(
                  <tr key={u.id}><td style={{fontWeight:500}}>{u.name}</td><td style={{color:'#64748b'}}>{u.username||'—'}</td><td>{getRoleChip(u.role)}</td><td><span className={`badge ${u.is_active?'b-green':'b-red'}`}>{u.is_active?'active':'inactive'}</span></td></tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h3>RB model</h3><p>Permissions available to the admin role</p></div></div>
            <div className="card-body">
              {adminPerms.map(p=>(
                <div key={p.permission} className="kv"><div><div style={{fontSize:13,fontWeight:600}}>{p.permission}</div><div style={{fontSize:12,color:'#64748b'}}>{p.description}</div></div></div>
              ))}
              {!adminPerms.length&&<div className="empty">No permissions available.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── DASHBOARD ROUTER ──
export function Dashboard({ onNavigate, onOpenModal, patientData, onDoctorRefreshReady }) {
  const { isAdmin, isDoctor } = useAuth()
  if (isAdmin) return <AdminDashboard onNavigate={onNavigate} />
  if (isDoctor) return <DoctorDashboard onNavigate={onNavigate} onDoctorRefreshReady={onDoctorRefreshReady} />
  return <PatientDashboard analyses={patientData.analyses} appointments={patientData.appointments} referrals={patientData.referrals} onNavigate={onNavigate} onOpenModal={onOpenModal} />
}

// ── ANALYSES ──
export function Analyses({ analyses }) {
  const { isAdmin, isDoctor, user } = useAuth()
  const toast = useToast()
  const [selected, setSelected] = useState(null)
  const [adminAnalyses, setAdminAnalyses] = useState([])
  const [adminOffset, setAdminOffset] = useState(0)
  const adminLimit = 20
  const [editId, setEditId] = useState(null), [editStatus, setEditStatus] = useState(''), [editNote, setEditNote] = useState(''), [editResults, setEditResults] = useState(''), [editDate, setEditDate] = useState(''), [editVisible, setEditVisible] = useState(true)

  const loadAdminAnalyses = async (nextOffset = adminOffset) => {
    const d = await apiGet('/admin/analyses', { limit: adminLimit, offset: nextOffset })
    setAdminAnalyses(mapAnalysesList(d.analyses || []))
    setAdminOffset(nextOffset)
  }
  useEffect(() => { if (isAdmin) loadAdminAnalyses(0) }, [isAdmin])

  if (isDoctor) return <DoctorAnalysesPage />

  if (isAdmin) {
    const openEdit = (a) => { setEditId(a.id); setEditStatus(a.statusRaw||a.status); setEditNote(a.labNote||''); setEditResults(formatAnalysisResultsText(a.results)); setEditDate(a.readyAt||a.date||''); setEditVisible(a.isVisibleToPatient) }
    const saveEdit = async () => {
      let results=[]
      try { results=parseAnalysisResultsText(editResults) } catch(e) { toast(e.message); return }
      try { await apiPut(`/admin/analyses/${editId}`,{status:editStatus,ready_at:editDate||null,lab_note:editNote||null,results,is_visible_to_patient:editVisible}); toast('Analysis updated.','success'); setEditId(null); await loadAdminAnalyses(adminOffset) } catch(e) { toast(e.message) }
    }
    return (
      <div className="page">
        <div className="admin-layout">
          <div className="card">
            <div className="card-head"><div><h3>Analyses queue</h3><p>Doctor orders, lab processing, and publication</p></div></div>
            <div className="card-body" style={{padding:0}}>
              <table className="tbl"><thead><tr><th>Patient</th><th>Analysis</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{adminAnalyses.slice(0,10).map(a=>(
                  <tr key={a.id}><td><div style={{fontWeight:600}}>{a.patientName||'Patient'}</div><div style={{fontSize:12,color:'#64748b'}}>{a.patientUsername||'—'}</div></td><td><div style={{fontWeight:500}}>{a.name}</div><div style={{fontSize:12,color:'#64748b'}}>{a.date||'—'} · {a.doctor||'—'}</div></td><td><span className={`badge ${badgeForStatus(a.status)}`}>{a.status}</span></td><td><button className="btn btn-secondary btn-sm" onClick={()=>openEdit(a)}>Update</button></td></tr>
                ))}{!adminAnalyses.length&&<tr><td colSpan="4"><div className="empty">No analyses in the queue.</div></td></tr>}</tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => loadAdminAnalyses(Math.max(0, adminOffset - adminLimit))} disabled={adminOffset === 0}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => loadAdminAnalyses(adminOffset + adminLimit)} disabled={adminAnalyses.length < adminLimit}>Next</button>
              </div>
            </div>
          </div>
        </div>
        {editId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Update analysis</h3><button className="modal-close" onClick={()=>setEditId(null)}>✕</button></div><div className="modal-bd"><div className="frow"><div className="fg"><label>Status</label><select value={editStatus} onChange={e=>setEditStatus(e.target.value)}><option value="назначен">Ordered</option><option value="в обработке">Processing</option><option value="готово">Ready</option></select></div><div className="fg"><label>Ready date</label><input type="date" value={editDate} onChange={e=>setEditDate(e.target.value)}/></div></div><div className="fg"><label>Lab note</label><textarea value={editNote} onChange={e=>setEditNote(e.target.value)} placeholder="Lab comment"/></div><div className="fg"><label>Results</label><textarea value={editResults} onChange={e=>setEditResults(e.target.value)} placeholder="Parameter | Value | Unit | Range | ok/abnormal"/></div><div className="note">Each result line: <code>Parameter | Value | Unit | Range | ok/abnormal</code></div><div className="fg" style={{marginTop:12}}><label><input type="checkbox" checked={editVisible} onChange={e=>setEditVisible(e.target.checked)} style={{marginRight:8}}/>Visible to patient</label></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditId(null)}>Cancel</button><button className="btn btn-primary" onClick={saveEdit}>Save</button></div></div></div>}
      </div>
    )
  }

  return (
    <div className="page">
      <div className="g2" style={{alignItems:'flex-start'}}>
        <div className="card">
          <div className="card-head"><h3>My analyses</h3></div>
          <div style={{padding:'6px 0'}}>
            {analyses.length ? analyses.map(item=>(
              <div key={item.id} onClick={()=>setSelected(item)} style={{padding:'13px 22px',cursor:'pointer',borderBottom:'1px solid #f8fafc',background:selected?.id===item.id?'#eff6ff':'transparent',transition:'background .1s'}}>
                <div style={{display:'flex',alignItems:'center',gap:11}}>
                  <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600,marginBottom:2}}>{item.name}</div><div style={{fontSize:12,color:'#64748b'}}>{item.date} · {item.doctor}</div></div>
                  <span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span>
                </div>
              </div>
            )) : <div className="empty">No analyses available for this user.</div>}
          </div>
        </div>
        <div>
          {selected ? (
            <div className="card">
              <div className="card-head"><div><h3>{selected.name}</h3><p>{selected.date} · {selected.doctor}</p></div><button className="btn btn-secondary btn-sm" onClick={()=>setSelected(null)}>✕</button></div>
              <div className="card-body" style={{padding:'8px 0 16px'}}>
                <div className="kv"><span style={{color:'#64748b'}}>Status</span><span className={`badge ${badgeForStatus(selected.status)}`}>{selected.status}</span></div>
                {selected.orderedAt&&<div className="kv"><span style={{color:'#64748b'}}>Ordered</span><span>{selected.orderedAt}</span></div>}
                {selected.readyAt&&<div className="kv"><span style={{color:'#64748b'}}>Ready at</span><span>{selected.readyAt}</span></div>}
                {selected.labNote&&<div className="note" style={{margin:'12px 0 0'}}>Lab note: {selected.labNote}</div>}
                {selected.doctorNote&&<div className="note" style={{margin:'12px 0 0'}}>Doctor note: {selected.doctorNote}</div>}
                {selected.results.length ? (
                  <table className="tbl" style={{marginTop:12}}><thead><tr><th>Parameter</th><th>Value</th><th>Normal range</th><th>Status</th></tr></thead>
                    <tbody>{selected.results.map((r,i)=>(
                      <tr key={i}><td style={{fontWeight:500}}>{r.param}</td><td style={{fontFamily:'monospace'}}>{r.val} {r.unit}</td><td style={{color:'#64748b'}}>{r.norm}</td><td><span className={`badge ${r.ok?'b-green':'b-red'}`}>{r.ok?'normal':'out of range'}</span></td></tr>
                    ))}</tbody>
                  </table>
                ) : <div className="empty" style={{marginTop:12}}>Results are not published yet.</div>}
              </div>
            </div>
          ) : <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:180,color:'#94a3b8',fontSize:14}}>← Select an analysis</div>}
        </div>
      </div>
    </div>
  )
}

function DoctorAnalysesPage() {
  return <DoctorDashboard onNavigate={()=>{}} />
}

// ── APPOINTMENTS ──
export function Appointments({ appointments, doctors, onRefresh, showModal, onCloseModal, onOpenModal }) {
  const { user } = useAuth()
  const toast = useToast()
  const [docId, setDocId] = useState(''), [date, setDate] = useState(getDefaultBookingDate()), [slots, setSlots] = useState([]), [selSlot, setSelSlot] = useState(''), [reason, setReason] = useState(''), [slotsLoading, setSlotsLoading] = useState(false)

  const loadSlots = async (did, dt) => {
    if (!did || !dt) return
    setSlotsLoading(true); setSelSlot(''); setSlots([])
    try { const d=await apiGet(`/doctors/${did}/availability`,{date:dt}); setSlots(d.available_slots||[]) } catch(e) { toast(e.message || 'Failed to load slots') }
    finally { setSlotsLoading(false) }
  }

  const submit = async () => {
    if (!docId) return toast('Please select a doctor.')
    if (!selSlot) return toast('Please select date and time.')
    try { await apiPost('/appointments',{user_id:user.id,doctor_user_id:Number(docId),date,time:selSlot,reason}); toast('Appointment request submitted.','success'); onCloseModal?.(); onRefresh() } catch(e) { toast(e.message) }
  }
  const cancelAppointment = async (appointmentId) => {
    try {
      await apiPatch(`/appointments/${appointmentId}/cancel`)
      toast('Appointment cancelled.', 'success')
      onRefresh()
    } catch (e) {
      toast(e.message)
    }
  }

  return (
    <div className="page">
      <div className="card">
        <div className="card-head"><h3>My appointments</h3><p>Upcoming doctor visits</p></div>
        <div className="card-body">
          {appointments.length ? appointments.map(item=>(
            <div key={item.id} className="appt">
              <div className="appt-date"><div className="appt-day">{item.day}</div><div className="appt-mon">{item.mon}</div></div>
              <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600}}>{item.doctor}</div><div style={{fontSize:12.5,color:'#64748b'}}>{item.spec} · {item.place}</div></div>
              <div style={{textAlign:'right'}}><div style={{fontSize:15,fontWeight:700,marginBottom:4}}>{item.time}</div><span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span>{item.status !== 'cancelled' && <button className="btn btn-secondary btn-sm" style={{marginTop:6}} onClick={() => cancelAppointment(item.id)}>Cancel</button>}</div>
            </div>
          )) : <div className="empty">No appointments yet.</div>}
        </div>
      </div>
      <div style={{marginTop:12}}><button className="btn btn-primary" onClick={onOpenModal}>+ Book appointment</button></div>
      {showModal&&(
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-hd"><h3>Book appointment</h3><button className="modal-close" onClick={onCloseModal}>✕</button></div>
            <div className="modal-bd">
              <div className="fg"><label>Doctor</label><select value={docId} onChange={e=>{setDocId(e.target.value);loadSlots(e.target.value,date)}}><option value="">Select doctor</option>{doctors.map(d=><option key={d.id} value={d.id}>{d.name}{d.department?' · '+d.department:''}</option>)}</select></div>
              <div className="frow">
                <div className="fg"><label>Date</label><input type="date" value={date} min={getLocalDateIso(0)} onChange={e=>{setDate(e.target.value);loadSlots(docId,e.target.value)}}/></div>
                <div className="fg"><label>Session time</label><select value={selSlot} onChange={e=>setSelSlot(e.target.value)} disabled={slotsLoading||!slots.length}><option value="">{slotsLoading?'Loading...':!docId||!date?'Select doctor and date first':!slots.length?'No free slots for this day':'Select time slot'}</option>{slots.map(s=><option key={s} value={s}>{s}</option>)}</select></div>
              </div>
              <div className="fg"><label>Reason</label><textarea value={reason} onChange={e=>setReason(e.target.value)} placeholder="Describe your symptoms..."/></div>
            </div>
            <div className="modal-ft"><button className="btn btn-secondary" onClick={onCloseModal}>Cancel</button><button className="btn btn-primary" onClick={submit}>Book</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── REFERRALS ──
export function Referrals({ referrals }) {
  return (
    <div className="page">
      <div className="card">
        <div className="card-head"><h3>Referrals</h3><p>Active and completed doctor referrals</p></div>
        <div className="card-body" style={{padding:0}}>
          <table className="tbl"><thead><tr><th>Referral</th><th>Issued by</th><th>Issue date</th><th>Deadline</th><th>Status</th></tr></thead>
            <tbody>{referrals.length ? referrals.map(r=>(
              <tr key={r.id}><td style={{fontWeight:500}}>{r.name}</td><td style={{color:'#64748b'}}>{r.from}</td><td style={{color:'#64748b'}}>{r.date}</td><td style={{color:'#64748b'}}>{r.deadline}</td><td><span className={`badge ${badgeForStatus(r.status)}`}>{r.status}</span></td></tr>
            )):<tr><td colSpan="5"><div className="empty">No referrals found.</div></td></tr>}</tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── AI ASSISTANT ──
export function AIAssistant() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([{role:'ai',text:'Hello! I am your medical AI assistant.\n\nI can:\n• Analyze your test results\n• Suggest which doctor to visit\n• Answer medical questions\n\nHow can I help you today?'}])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const msgsRef = useRef(null)

  const scrollDown = () => { if(msgsRef.current) msgsRef.current.scrollTop=msgsRef.current.scrollHeight }

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev=>[...prev,{role:'user',text}])
    setLoading(true)
    try {
      const d = await apiPost('/ai/chat',{user_id:user?.id,message:text,context:'You are a medical AI assistant. Reply briefly, clearly, and in English with practical recommendations.'})
      setMessages(prev=>[...prev,{role:'ai',text:d.reply||'Could not get a response.'}])
    } catch(e) { setMessages(prev=>[...prev,{role:'ai',text:'Connection error: '+e.message}]) }
    setLoading(false)
    setTimeout(scrollDown,50)
  }

  return (
    <div className="page">
      <div className="card">
        <div className="card-head">
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <div style={{width:38,height:38,borderRadius:'50%',background:'linear-gradient(135deg,#667eea,#764ba2)',display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontWeight:700,fontSize:12}}>AI</div>
            <div><h3>AI Assistant</h3><p style={{color:'#10b981'}}>● online · Gemini 2.0 Flash</p></div>
          </div>
        </div>
        <div className="chat-wrap">
          <div className="chat-msgs" ref={msgsRef}>
            {messages.map((m,i)=>(
              <div key={i} className={`msg ${m.role}`}>
                <div className={`msg-av ${m.role}`}>{m.role==='ai'?'AI':(user?.initials||'PT')}</div>
                <div className="msg-bbl">{m.text}</div>
              </div>
            ))}
            {loading&&<div className="msg ai"><div className="msg-av ai">AI</div><div className="msg-bbl"><div className="typing"><span/><span/><span/></div></div></div>}
          </div>
          <div className="sugg">
            {['What does high cholesterol mean?','Please analyze my test results','I have headache and fatigue, which doctor should I visit?'].map(q=>(
              <button key={q} onClick={()=>{setInput(q)}}>{q}</button>
            ))}
          </div>
          <div className="chat-input-area">
            <input className="chat-input" value={input} onChange={e=>setInput(e.target.value)} placeholder="Describe symptoms or ask a question..." onKeyDown={e=>e.key==='Enter'&&send()}/>
            <button className="send-btn" onClick={send}><svg width="15" height="15" viewBox="0 0 24 24" fill="white"><path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/></svg></button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── PROFILE ──
export function Profile() {
  const { user, setContext, context } = useAuth()
  const toast = useToast()
  const [data, setData] = useState({})
  const [editing, setEditing] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(()=>{ if(user?.id) apiGet('/user/'+user.id).then(u=>setData(mapUser(u))) },[user?.id])

  const save = async () => {
    setLoading(true)
    try {
      const clean = (value) => (value === '—' ? '' : String(value || '').trim())
      const payload={name:clean(data.name),dob:clean(data.dob)||null,phone:clean(data.phone)||null,email:clean(data.email)||null,address:clean(data.address)||null,department:clean(data.department)||null,iin:clean(data.iin)||null,blood_type:clean(data.blood)||null,height:data.height?parseFloat(data.height):null,weight:data.weight?parseFloat(data.weight):null}
      Object.keys(payload).forEach(k=>{if(payload[k]===null&&k!=='height'&&k!=='weight')delete payload[k]})
      await apiPut('/user/'+user.id,payload)
      setContext({...context,user:{...context.user,...payload,name:payload.name||user.name}})
      toast('Profile saved.','success'); setEditing(false)
    } catch(e) { toast(e.message) }
    setLoading(false)
  }

  const bmi = (() => { const h=Number(data.height),w=Number(data.weight); if(!h||!w)return '—'; return (w/((h/100)**2)).toFixed(1) })()

  const Field = ({label,field,type='text'}) => (
    <div style={{marginBottom:12}}>
      <div style={{fontSize:12,color:'#94a3b8',marginBottom:4}}>{label}</div>
      {editing ? <input style={{width:'100%',padding:'8px 11px',border:'1px solid #e2e8f0',borderRadius:7,fontSize:13.5,fontFamily:'inherit'}} type={type} value={data[field]||''} onChange={e=>setData(p=>({...p,[field]:e.target.value}))}/> : <div style={{fontSize:14,fontWeight:500}}>{data[field]||'—'}</div>}
    </div>
  )

  return (
    <div className="page">
      <div className="profile-grid" style={{alignItems:'flex-start'}}>
        <div className="card">
          <div style={{padding:22,display:'flex',alignItems:'center',gap:18,borderBottom:'1px solid #e2e8f0'}}>
            <div style={{width:68,height:68,borderRadius:'50%',background:'#2563eb',display:'flex',alignItems:'center',justifyContent:'center',fontSize:20,fontWeight:700,color:'#fff'}}>{data.initials||'PT'}</div>
            <div><h2 style={{fontSize:18,marginBottom:6}}>{data.name||user?.name}</h2><div className="inline-badges"><span className="badge b-blue">Username: {data.username||'—'}</span>{getRoleChip(user?.role)}</div></div>
          </div>
          <div className="card-body">
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14}}>
              <div style={{fontSize:11,textTransform:'uppercase',letterSpacing:0.5,color:'#94a3b8',fontWeight:500}}>Personal info</div>
              <button className="btn btn-secondary btn-sm" onClick={()=>editing?save():setEditing(true)} disabled={loading}>{editing?(loading?'Saving...':'Save'):'Edit'}</button>
            </div>
            {[['Name','name'],['Date of birth','dob'],['Phone','phone'],['Email','email'],['Address','address']].map(([l,f])=><Field key={f} label={l} field={f}/>)}
          </div>
        </div>
        <div className="stack">
          <div className="card"><div className="card-body">
            <div style={{fontSize:11,textTransform:'uppercase',letterSpacing:0.5,color:'#94a3b8',fontWeight:500,marginBottom:14}}>Medical data</div>
            {[['IIN','iin'],['Height (cm)','height'],['Weight (kg)','weight'],['Blood type','blood']].map(([l,f])=><Field key={f} label={l} field={f} type={f==='height'||f==='weight'?'number':'text'}/>)}
            <div className="kv"><span style={{fontSize:13,color:'#64748b'}}>BMI</span><span style={{fontSize:13,fontWeight:500}}>{bmi==='—'?'—':`${bmi} — Normal`}</span></div>
          </div></div>
          <div className="card"><div className="card-body">
            <div style={{fontSize:11,textTransform:'uppercase',letterSpacing:0.5,color:'#94a3b8',fontWeight:500,marginBottom:14}}>Account context</div>
            {[['Role',formatRole(user?.role)],['Department',user?.department||'—'],['Permissions',(context?.permissions||[]).join(', ')||'—']].map(([k,v])=>(
              <div key={k} className="kv"><span style={{fontSize:13,color:'#64748b'}}>{k}</span><span style={{fontSize:13,fontWeight:500,textAlign:'right'}}>{v}</span></div>
            ))}
          </div></div>
        </div>
      </div>
    </div>
  )
}

// ── ADMIN PANEL ──
export function AdminPanel() {
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [analyses, setAnalyses] = useState([])
  const [rbac, setRbac] = useState([])
  const [usersOffset, setUsersOffset] = useState(0)
  const [analysesOffset, setAnalysesOffset] = useState(0)
  const pageLimit = 20
  const [form, setForm] = useState({name:'',username:'',password:'',role:'user',email:'',phone:'',department:''})
  const [editPwId, setEditPwId] = useState(null), [newPw, setNewPw] = useState(''), [confPw, setConfPw] = useState('')
  const [editAnId, setEditAnId] = useState(null), [anStatus, setAnStatus] = useState(''), [anNote, setAnNote] = useState(''), [anResults, setAnResults] = useState(''), [anDate, setAnDate] = useState(''), [anVisible, setAnVisible] = useState(true)

  const load = async (nextUsersOffset = usersOffset, nextAnalysesOffset = analysesOffset) => {
    const [u,a,r]=await Promise.all([apiGet('/admin/users', { limit: pageLimit, offset: nextUsersOffset }),apiGet('/admin/analyses', { limit: pageLimit, offset: nextAnalysesOffset }),apiGet('/rbac/model')])
    setUsers((u.users||[]).map(mapUser)); setAnalyses(mapAnalysesList(a.analyses||[])); setRbac(r.roles||[])
    setUsersOffset(nextUsersOffset)
    setAnalysesOffset(nextAnalysesOffset)
  }
  useEffect(()=>{load()},[])

  const createUser = async () => {
    if(!form.name||!form.username||!form.password){toast('Name, username and password are required.');return}
    try{await apiPost('/admin/users',form);toast('User account created.','success');load();setForm({name:'',username:'',password:'',role:'user',email:'',phone:'',department:''})}catch(e){toast(e.message)}
  }
  const applyRole = async (uid,role) => { try{await apiPut('/admin/users/'+uid,{role});toast('Role updated.','success');load()}catch(e){toast(e.message)} }
  const toggleStatus = async (u) => { try{await apiPut('/admin/users/'+u.id,{is_active:!u.is_active});toast('Status updated.','success');load()}catch(e){toast(e.message)} }
  const resetPw = async () => {
    if(!newPw){toast('Enter a new password.');return} if(newPw.length<6){toast('Password must be at least 6 characters.');return} if(newPw!==confPw){toast('Passwords do not match.');return}
    try{await apiPut('/admin/users/'+editPwId,{password:newPw});toast('Password updated.','success');setEditPwId(null)}catch(e){toast(e.message)}
  }
  const openAnEdit = (a) => { setEditAnId(a.id);setAnStatus(a.statusRaw||a.status);setAnNote(a.labNote||'');setAnResults(formatAnalysisResultsText(a.results));setAnDate(a.readyAt||a.date||'');setAnVisible(a.isVisibleToPatient) }
  const saveAn = async () => {
    let results=[]
    try{results=parseAnalysisResultsText(anResults)}catch(e){toast(e.message);return}
    try{await apiPut(`/admin/analyses/${editAnId}`,{status:anStatus,ready_at:anDate||null,lab_note:anNote||null,results,is_visible_to_patient:anVisible});toast('Analysis updated.','success');setEditAnId(null);load()}catch(e){toast(e.message)}
  }

  return (
    <div className="page">
      <div className="admin-layout">
        <div className="stack">
          <div className="card" id="new-user-form">
            <div className="card-head"><div><h3>Create new user</h3><p>Create a patient, doctor, or administrator with login and password</p></div></div>
            <div className="card-body">
              <div className="frow">
                <div className="fg"><label>Full name</label><input value={form.name} onChange={e=>setForm(p=>({...p,name:e.target.value}))} placeholder="Aruzhan Sarsenova"/></div>
                <div className="fg"><label>Username</label><input value={form.username} onChange={e=>setForm(p=>({...p,username:e.target.value}))} placeholder="aruzhan.user"/></div>
              </div>
              <div className="frow">
                <div className="fg"><label>Password</label><input type="password" value={form.password} onChange={e=>setForm(p=>({...p,password:e.target.value}))} placeholder="Create a password"/></div>
                <div className="fg"><label>Role</label><select value={form.role} onChange={e=>setForm(p=>({...p,role:e.target.value}))}><option value="user">Patient</option><option value="doctor">Doctor</option><option value="admin">Admin</option></select></div>
              </div>
              <div className="frow">
                <div className="fg"><label>Email</label><input value={form.email} onChange={e=>setForm(p=>({...p,email:e.target.value}))} placeholder="user@densaulyq.local"/></div>
                <div className="fg"><label>Phone</label><input value={form.phone} onChange={e=>setForm(p=>({...p,phone:e.target.value}))} placeholder="+7 700 000 00 00"/></div>
              </div>
              <div className="fg"><label>Department</label><input value={form.department} onChange={e=>setForm(p=>({...p,department:e.target.value}))} placeholder="Patient care"/></div>
              <div className="inline-actions"><button className="btn btn-primary" onClick={createUser}>Create account</button></div>
            </div>
          </div>
          <div className="card">
            <div className="card-head"><div><h3>Users from DB</h3><p>Role and access management</p></div></div>
            <div className="card-body" style={{padding:0}}>
              <table className="tbl"><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{users.map(u=>(
                  <tr key={u.id}>
                    <td><div style={{fontWeight:600}}>{u.name}</div><div style={{fontSize:12,color:'#64748b'}}>{u.email||'—'}</div></td>
                    <td style={{color:'#64748b'}}>{u.username||'—'}</td>
                    <td>{getRoleChip(u.role)}</td>
                    <td><span className={`badge ${u.is_active?'b-green':'b-red'}`}>{u.is_active?'active':'inactive'}</span></td>
                    <td>
                      <div className="inline-actions">
                        <select defaultValue={u.role} onChange={e=>applyRole(u.id,e.target.value)} style={{padding:'5px 8px',border:'1px solid #e2e8f0',borderRadius:7,fontSize:12,background:'#fff'}}>
                          <option value="user">Patient</option><option value="doctor">Doctor</option><option value="admin">Admin</option>
                        </select>
                        <button className="btn btn-secondary btn-sm" onClick={()=>toggleStatus(u)}>{u.is_active?'Deactivate':'Activate'}</button>
                        <button className="btn btn-secondary btn-sm" onClick={()=>{setEditPwId(u.id);setNewPw('');setConfPw('')}}>Reset password</button>
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => load(Math.max(0, usersOffset - pageLimit), analysesOffset)} disabled={usersOffset === 0}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => load(usersOffset + pageLimit, analysesOffset)} disabled={users.length < pageLimit}>Next</button>
              </div>
            </div>
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h3>Analyses queue</h3><p>Doctor orders, lab processing, and publication</p></div></div>
            <div className="card-body" style={{padding:0}}>
              <table className="tbl"><thead><tr><th>Patient</th><th>Analysis</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{analyses.slice(0,10).map(a=>(
                  <tr key={a.id}><td><div style={{fontWeight:600}}>{a.patientName||'Patient'}</div><div style={{fontSize:12,color:'#64748b'}}>{a.patientUsername||'—'}</div></td><td><div style={{fontWeight:500}}>{a.name}</div><div style={{fontSize:12,color:'#64748b'}}>{a.date||'—'} · {a.doctor||'—'}</div></td><td><span className={`badge ${badgeForStatus(a.status)}`}>{a.status}</span></td><td><button className="btn btn-secondary btn-sm" onClick={()=>openAnEdit(a)}>Update</button></td></tr>
                ))}{!analyses.length&&<tr><td colSpan="4"><div className="empty">No analyses in the queue.</div></td></tr>}</tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => load(usersOffset, Math.max(0, analysesOffset - pageLimit))} disabled={analysesOffset === 0}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => load(usersOffset, analysesOffset + pageLimit)} disabled={analyses.length < pageLimit}>Next</button>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-head"><div><h3>RB model</h3><p>Role-based permissions exposed by API</p></div></div>
            <div className="card-body">
              {rbac.map(role=>(
                <div key={role.role} style={{marginBottom:18}}>
                  <div className="inline-badges" style={{marginBottom:10}}>{getRoleChip(role.role)}<span style={{fontSize:12,color:'#64748b'}}>{role.permissions.length} permissions</span></div>
                  {role.permissions.map(p=><div key={p.permission} className="kv"><div><div style={{fontSize:13,fontWeight:600}}>{p.permission}</div><div style={{fontSize:12,color:'#64748b'}}>{p.description}</div></div></div>)}
                </div>
              ))}
            </div>
          </div>
          <div className="note">Пользователь входит через единый <code>username/password</code>. Роль <code>user</code> открывает patient portal, <code>doctor</code> — doctor dashboard, <code>admin</code> — admin panel.</div>
        </div>
      </div>
      {editPwId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Reset password</h3><button className="modal-close" onClick={()=>setEditPwId(null)}>✕</button></div><div className="modal-bd"><div className="fg"><label>New password</label><input type="password" value={newPw} onChange={e=>setNewPw(e.target.value)} placeholder="Enter new password"/></div><div className="fg"><label>Confirm password</label><input type="password" value={confPw} onChange={e=>setConfPw(e.target.value)} placeholder="Repeat new password"/></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditPwId(null)}>Cancel</button><button className="btn btn-primary" onClick={resetPw}>Save</button></div></div></div>}
      {editAnId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Update analysis</h3><button className="modal-close" onClick={()=>setEditAnId(null)}>✕</button></div><div className="modal-bd"><div className="frow"><div className="fg"><label>Status</label><select value={anStatus} onChange={e=>setAnStatus(e.target.value)}><option value="назначен">Ordered</option><option value="в обработке">Processing</option><option value="готово">Ready</option></select></div><div className="fg"><label>Ready date</label><input type="date" value={anDate} onChange={e=>setAnDate(e.target.value)}/></div></div><div className="fg"><label>Lab note</label><textarea value={anNote} onChange={e=>setAnNote(e.target.value)} placeholder="Lab comment"/></div><div className="fg"><label>Results</label><textarea value={anResults} onChange={e=>setAnResults(e.target.value)} placeholder="Parameter | Value | Unit | Range | ok/abnormal"/></div><div className="note">Each result line: <code>Parameter | Value | Unit | Range | ok/abnormal</code></div><div className="fg" style={{marginTop:12}}><label><input type="checkbox" checked={anVisible} onChange={e=>setAnVisible(e.target.checked)} style={{marginRight:8}}/>Visible to patient</label></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditAnId(null)}>Cancel</button><button className="btn btn-primary" onClick={saveAn}>Save</button></div></div></div>}
    </div>
  )
}
