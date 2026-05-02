import { useState, useRef } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiPost } from '../../api.js'

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
