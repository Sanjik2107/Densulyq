import { useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { apiGet, apiPatch, apiPost } from '../../api.js'
import { badgeForStatus, getLocalDateIso, getDefaultBookingDate } from '../../utils.jsx'

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
