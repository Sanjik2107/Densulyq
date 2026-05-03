import { useState, useEffect } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { apiGet, apiPost, apiPut } from '../../api.js'
import { badgeForStatus, getRoleChip, mapAnalysesList, mapAppointmentsList, mapReferralsList, mapUser, getLocalDateIso, getDefaultBookingDate, ANALYSIS_NAME_OPTIONS } from '../../utils.jsx'

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
  const upcomingAppointments = appointments.filter(a=>a.isUpcomingActive)
  const nextAppt = upcomingAppointments[0]
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
              {upcomingAppointments.length ? upcomingAppointments.slice(0,3).map(item=>(
                <div key={item.id} className="appt">
                  <div className="appt-date"><div className="appt-day">{item.day}</div><div className="appt-mon">{item.mon}</div></div>
                  <div style={{flex:1}}><div style={{fontSize:14,fontWeight:600}}>{item.doctor}</div><div style={{fontSize:12,color:'#64748b'}}>{item.spec} · {item.place}</div></div>
                  <div style={{textAlign:'right'}}><div style={{fontSize:14,fontWeight:600}}>{item.time}</div><span className={`badge ${badgeForStatus(item.status)}`}>{item.status}</span></div>
                </div>
              )) : <div className="empty">No upcoming appointments.</div>}
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
export function DoctorDashboard({ onDoctorRefreshReady }) {
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

  // Initial doctor dashboard fetch only.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadPatients(0) }, [])
  useEffect(() => {
    if (!onDoctorRefreshReady) return
    onDoctorRefreshReady(() => () => loadPatients(offset))
    // Parent stores this callback for the topbar refresh button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
            <div className="card">
              <div className="card-head"><div><h3>Referrals</h3><p>Active directions linked to this patient</p></div></div>
              <div className="card-body" style={{paddingTop:10}}>
                {activeRefs.length ? activeRefs.map(ref => (
                  <div key={ref.id} className="li">
                    <div className="li-icon" style={{background:'#d1fae5',color:'#059669',fontSize:12,fontWeight:700}}>REF</div>
                    <div style={{flex:1}}><div style={{fontSize:13.5,fontWeight:500}}>{ref.name}</div><div style={{fontSize:12,color:'#64748b'}}>from {ref.from || '—'} · until {ref.deadline || '—'}</div></div>
                    <span className={`badge ${badgeForStatus(ref.status)}`}>{ref.status}</span>
                  </div>
                )) : <div className="empty">No referrals found.</div>}
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
  const [rbac, setRbac] = useState([])

  useEffect(() => {
    Promise.all([apiGet('/admin/users'), apiGet('/rbac/model')]).then(([u,r])=>{
      setUsers((u.users||[]).map(mapUser)); setStats(u.stats||{}); setRbac(r.roles||[])
    })
  }, [])

  const adminRole = rbac.find(r=>r.role==='admin')
  const adminPerms = adminRole?.permissions||[]

  return (
    <div className="page">
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:16,marginBottom:18}}>
        {[{lbl:'Total users',val:stats.total_users||0,sub:'All accounts in database',ico:'ALL',bg:'#dbeafe',c:'#2563eb'},{lbl:'Admins',val:stats.admins||0,sub:'Privileged accounts',ico:'ADM',bg:'#ede9fe',c:'#7c3aed'},{lbl:'Doctors',val:stats.doctors||0,sub:'Clinical staff accounts',ico:'DOC',bg:'#f3e8ff',c:'#9333ea'},{lbl:'Patients',val:stats.users||0,sub:'Standard portal accounts',ico:'USR',bg:'#d1fae5',c:'#059669'},{lbl:'Active',val:stats.active_users||0,sub:'Accounts with access',ico:'ON',bg:'#fef3c7',c:'#d97706'}].map(card=>(
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
  if (isDoctor) return <DoctorDashboard onDoctorRefreshReady={onDoctorRefreshReady} />
  return <PatientDashboard analyses={patientData.analyses} appointments={patientData.appointments} referrals={patientData.referrals} onNavigate={onNavigate} onOpenModal={onOpenModal} />
}
