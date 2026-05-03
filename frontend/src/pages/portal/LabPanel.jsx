import { useEffect, useState } from 'react'
import { apiGet, apiPut } from '../../api.js'
import { API_BASE, badgeForStatus, formatAnalysisResultsText, getAnalysisStatusOptions, mapAnalysesList, parseAnalysisResultsText } from '../../utils.jsx'
import { useToast } from '../../context/ToastContext.jsx'

export function LabPanel() {
  const toast = useToast()
  const [analyses, setAnalyses] = useState([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 20
  const [editAnId, setEditAnId] = useState(null), [anStatus, setAnStatus] = useState(''), [anCurrentStatus, setAnCurrentStatus] = useState(''), [anNote, setAnNote] = useState(''), [anResults, setAnResults] = useState(''), [anDate, setAnDate] = useState(''), [anVisible, setAnVisible] = useState(true)

  const load = async (nextOffset = offset) => {
    try {
      const data = await apiGet('/lab/analyses', { limit, offset: nextOffset, query, status })
      setAnalyses(mapAnalysesList(data.analyses || []))
      setOffset(nextOffset)
    } catch (e) { toast(e.message) }
  }

  useEffect(() => { load(0) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const openEdit = (a) => {
    const rawStatus = a.statusRaw || a.status
    setEditAnId(a.id); setAnStatus(rawStatus); setAnCurrentStatus(rawStatus); setAnNote(a.labNote || '')
    setAnResults(formatAnalysisResultsText(a.results)); setAnDate(a.readyAt || a.date || ''); setAnVisible(a.isVisibleToPatient)
  }

  const saveAn = async () => {
    let results
    try { results = parseAnalysisResultsText(anResults) } catch (e) { toast(e.message); return }
    try {
      await apiPut(`/lab/analyses/${editAnId}`, { status: anStatus, ready_at: anDate || null, lab_note: anNote || null, results, is_visible_to_patient: anVisible })
      toast('Analysis updated.', 'success')
      setEditAnId(null)
      load(offset)
    } catch (e) { toast(e.message) }
  }

  const exportCsv = () => {
    const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE
    window.open(base + '/lab/analyses/export', '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="page">
      <div className="card">
        <div className="card-head">
          <div><h3>Laboratory queue</h3><p>Doctor orders, processing, result entry, and patient publication</p></div>
          <div className="inline-actions"><button className="btn btn-secondary btn-sm" onClick={exportCsv}>Export CSV</button></div>
        </div>
        <div className="card-body">
          <div className="frow">
            <div className="fg"><label>Search</label><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Patient, username, analysis"/></div>
            <div className="fg"><label>Status</label><select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option><option value="назначен">Ordered</option><option value="в обработке">Processing</option><option value="готово">Ready</option><option value="проверено">Reviewed</option></select></div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={()=>load(0)}>Apply filters</button>
        </div>
        <div className="card-body" style={{padding:0}}>
          <table className="tbl"><thead><tr><th>Patient</th><th>Analysis</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>{analyses.map(a=>(
              <tr key={a.id}><td><div style={{fontWeight:600}}>{a.patientName||'Patient'}</div><div style={{fontSize:12,color:'#64748b'}}>{a.patientUsername||'—'}</div></td><td><div style={{fontWeight:500}}>{a.name}</div><div style={{fontSize:12,color:'#64748b'}}>{a.date||'—'} · {a.doctor||'—'}</div></td><td><span className={`badge ${badgeForStatus(a.status)}`}>{a.status}</span></td><td>{a.statusRaw==='проверено'?<span className="badge b-gray">Reviewed</span>:<button className="btn btn-secondary btn-sm" onClick={()=>openEdit(a)}>Update</button>}</td></tr>
            ))}{!analyses.length&&<tr><td colSpan="4"><div className="empty">No analyses in the queue.</div></td></tr>}</tbody>
          </table>
          <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
            <button className="btn btn-secondary btn-sm" onClick={() => load(Math.max(0, offset - limit))} disabled={offset === 0}>Prev</button>
            <button className="btn btn-secondary btn-sm" onClick={() => load(offset + limit)} disabled={analyses.length < limit}>Next</button>
          </div>
        </div>
      </div>
      {editAnId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Update analysis</h3><button className="modal-close" onClick={()=>setEditAnId(null)}>x</button></div><div className="modal-bd"><div className="frow"><div className="fg"><label>Status</label><select value={anStatus} onChange={e=>setAnStatus(e.target.value)}>{getAnalysisStatusOptions(anCurrentStatus).map(option=><option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div className="fg"><label>Ready date</label><input type="date" value={anDate} onChange={e=>setAnDate(e.target.value)}/></div></div><div className="fg"><label>Lab note</label><textarea value={anNote} onChange={e=>setAnNote(e.target.value)} placeholder="Lab comment"/></div><div className="fg"><label>Results</label><textarea value={anResults} onChange={e=>setAnResults(e.target.value)} placeholder="Parameter | Value | Unit | Range | ok/abnormal"/></div><div className="note">Each result line: <code>Parameter | Value | Unit | Range | ok/abnormal</code></div><div className="fg" style={{marginTop:12}}><label><input type="checkbox" checked={anVisible} onChange={e=>setAnVisible(e.target.checked)} style={{marginRight:8}}/>Visible to patient</label></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditAnId(null)}>Cancel</button><button className="btn btn-primary" onClick={saveAn}>Save</button></div></div></div>}
    </div>
  )
}
