import { useState, useEffect } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { apiGet, apiPut } from '../../api.js'
import { badgeForStatus, mapAnalysesList, formatAnalysisResultsText, getAnalysisStatusOptions, parseAnalysisResultsText } from '../../utils.jsx'
import { DoctorDashboard } from './Dashboard.jsx'

// ── ANALYSES ──
export function Analyses({ analyses }) {
  const { isAdmin, isDoctor } = useAuth()
  const toast = useToast()
  const [selected, setSelected] = useState(null)
  const [adminAnalyses, setAdminAnalyses] = useState([])
  const [adminOffset, setAdminOffset] = useState(0)
  const adminLimit = 20
  const [editId, setEditId] = useState(null), [editStatus, setEditStatus] = useState(''), [editCurrentStatus, setEditCurrentStatus] = useState(''), [editNote, setEditNote] = useState(''), [editResults, setEditResults] = useState(''), [editDate, setEditDate] = useState(''), [editVisible, setEditVisible] = useState(true)

  const loadAdminAnalyses = async (nextOffset = adminOffset) => {
    const d = await apiGet('/admin/analyses', { limit: adminLimit, offset: nextOffset })
    setAdminAnalyses(mapAnalysesList(d.analyses || []))
    setAdminOffset(nextOffset)
  }
  // Initial admin analysis queue fetch.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (isAdmin) loadAdminAnalyses(0) }, [isAdmin])

  if (isDoctor) return <DoctorAnalysesPage />

  if (isAdmin) {
    const openEdit = (a) => { const rawStatus = a.statusRaw||a.status; setEditId(a.id); setEditStatus(rawStatus); setEditCurrentStatus(rawStatus); setEditNote(a.labNote||''); setEditResults(formatAnalysisResultsText(a.results)); setEditDate(a.readyAt||a.date||''); setEditVisible(a.isVisibleToPatient) }
    const saveEdit = async () => {
      let results
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
                  <tr key={a.id}><td><div style={{fontWeight:600}}>{a.patientName||'Patient'}</div><div style={{fontSize:12,color:'#64748b'}}>{a.patientUsername||'—'}</div></td><td><div style={{fontWeight:500}}>{a.name}</div><div style={{fontSize:12,color:'#64748b'}}>{a.date||'—'} · {a.doctor||'—'}</div></td><td><span className={`badge ${badgeForStatus(a.status)}`}>{a.status}</span></td><td>{a.statusRaw==='проверено'?<span className="badge b-gray">Reviewed</span>:<button className="btn btn-secondary btn-sm" onClick={()=>openEdit(a)}>Update</button>}</td></tr>
                ))}{!adminAnalyses.length&&<tr><td colSpan="4"><div className="empty">No analyses in the queue.</div></td></tr>}</tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => loadAdminAnalyses(Math.max(0, adminOffset - adminLimit))} disabled={adminOffset === 0}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => loadAdminAnalyses(adminOffset + adminLimit)} disabled={adminAnalyses.length < adminLimit}>Next</button>
              </div>
            </div>
          </div>
        </div>
        {editId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Update analysis</h3><button className="modal-close" onClick={()=>setEditId(null)}>✕</button></div><div className="modal-bd"><div className="frow"><div className="fg"><label>Status</label><select value={editStatus} onChange={e=>setEditStatus(e.target.value)}>{getAnalysisStatusOptions(editCurrentStatus).map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div className="fg"><label>Ready date</label><input type="date" value={editDate} onChange={e=>setEditDate(e.target.value)}/></div></div><div className="fg"><label>Lab note</label><textarea value={editNote} onChange={e=>setEditNote(e.target.value)} placeholder="Lab comment"/></div><div className="fg"><label>Results</label><textarea value={editResults} onChange={e=>setEditResults(e.target.value)} placeholder="Parameter | Value | Unit | Range | ok/abnormal"/></div><div className="note">Each result line: <code>Parameter | Value | Unit | Range | ok/abnormal</code></div><div className="fg" style={{marginTop:12}}><label><input type="checkbox" checked={editVisible} onChange={e=>setEditVisible(e.target.checked)} style={{marginRight:8}}/>Visible to patient</label></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditId(null)}>Cancel</button><button className="btn btn-primary" onClick={saveEdit}>Save</button></div></div></div>}
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
  return <DoctorDashboard />
}
