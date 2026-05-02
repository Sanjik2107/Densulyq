import { badgeForStatus } from '../../utils.jsx'

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
