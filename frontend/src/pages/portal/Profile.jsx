import { useState, useEffect } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { useToast } from '../../context/ToastContext.jsx'
import { apiGet, apiPut } from '../../api.js'
import { getRoleChip, formatRole, mapUser } from '../../utils.jsx'

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
