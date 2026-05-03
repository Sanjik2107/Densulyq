import { useState, useEffect } from 'react'
import { useToast } from '../../context/ToastContext.jsx'
import { apiGet, apiPost, apiPut } from '../../api.js'
import { API_BASE, getRoleChip, mapUser } from '../../utils.jsx'

// ── ADMIN PANEL ──
export function AdminPanel() {
  const toast = useToast()
  const [users, setUsers] = useState([])
  const [audit, setAudit] = useState([])
  const [rbac, setRbac] = useState([])
  const [usersOffset, setUsersOffset] = useState(0)
  const [userQuery, setUserQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const pageLimit = 20
  const [form, setForm] = useState({name:'',username:'',password:'',role:'user',email:'',phone:'',department:''})
  const [editPwId, setEditPwId] = useState(null), [newPw, setNewPw] = useState(''), [confPw, setConfPw] = useState('')

  const load = async (nextUsersOffset = usersOffset) => {
    const [u,a,r]=await Promise.all([
      apiGet('/admin/users', { limit: pageLimit, offset: nextUsersOffset, query: userQuery, role: roleFilter }),
      apiGet('/admin/audit-log', { limit: 12 }),
      apiGet('/rbac/model'),
    ])
    setUsers((u.users||[]).map(mapUser)); setAudit(a.audit||[]); setRbac(r.roles||[])
    setUsersOffset(nextUsersOffset)
  }
  // Initial admin panel fetch.
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
  const exportUsers = () => {
    const base = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE
    window.open(base + '/admin/users/export', '_blank', 'noopener,noreferrer')
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
                <div className="fg"><label>Role</label><select value={form.role} onChange={e=>setForm(p=>({...p,role:e.target.value}))}><option value="user">Patient</option><option value="doctor">Doctor</option><option value="lab">Lab</option><option value="admin">Admin</option></select></div>
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
            <div className="card-head"><div><h3>Users from DB</h3><p>Role and access management</p></div><button className="btn btn-secondary btn-sm" onClick={exportUsers}>Export CSV</button></div>
            <div className="card-body">
              <div className="frow">
                <div className="fg"><label>Search</label><input value={userQuery} onChange={e=>setUserQuery(e.target.value)} placeholder="Name, username, email, phone"/></div>
                <div className="fg"><label>Role</label><select value={roleFilter} onChange={e=>setRoleFilter(e.target.value)}><option value="">All roles</option><option value="user">Patient</option><option value="doctor">Doctor</option><option value="lab">Lab</option><option value="admin">Admin</option></select></div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={()=>load(0)}>Apply filters</button>
            </div>
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
                          <option value="user">Patient</option><option value="doctor">Doctor</option><option value="lab">Lab</option><option value="admin">Admin</option>
                        </select>
                        <button className="btn btn-secondary btn-sm" onClick={()=>toggleStatus(u)}>{u.is_active?'Deactivate':'Activate'}</button>
                        <button className="btn btn-secondary btn-sm" onClick={()=>{setEditPwId(u.id);setNewPw('');setConfPw('')}}>Reset password</button>
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              <div style={{display:'flex',justifyContent:'space-between',padding:'10px 16px'}}>
                <button className="btn btn-secondary btn-sm" onClick={() => load(Math.max(0, usersOffset - pageLimit))} disabled={usersOffset === 0}>Prev</button>
                <button className="btn btn-secondary btn-sm" onClick={() => load(usersOffset + pageLimit)} disabled={users.length < pageLimit}>Next</button>
              </div>
            </div>
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-head"><div><h3>Audit log</h3><p>Recent security and workflow events</p></div></div>
            <div className="card-body">
              {audit.length ? audit.map(item=>(
                <div key={item.id} className="kv"><div><div style={{fontSize:13,fontWeight:600}}>{item.action}</div><div style={{fontSize:12,color:'#64748b'}}>{item.actor_username||'system'} · {item.entity_type||'—'} #{item.entity_id||'—'}</div></div><span style={{fontSize:12,color:'#64748b'}}>{String(item.created_at).slice(0,16)}</span></div>
              )) : <div className="empty">No audit events yet.</div>}
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
          <div className="note">Пользователь входит через единый <code>username/password</code>. Роль <code>lab</code> обрабатывает анализы, <code>admin</code> управляет доступом и аудитом.</div>
        </div>
      </div>
      {editPwId&&<div className="modal-overlay"><div className="modal"><div className="modal-hd"><h3>Reset password</h3><button className="modal-close" onClick={()=>setEditPwId(null)}>✕</button></div><div className="modal-bd"><div className="fg"><label>New password</label><input type="password" value={newPw} onChange={e=>setNewPw(e.target.value)} placeholder="Enter new password"/></div><div className="fg"><label>Confirm password</label><input type="password" value={confPw} onChange={e=>setConfPw(e.target.value)} placeholder="Repeat new password"/></div></div><div className="modal-ft"><button className="btn btn-secondary" onClick={()=>setEditPwId(null)}>Cancel</button><button className="btn btn-primary" onClick={resetPw}>Save</button></div></div></div>}
    </div>
  )
}
