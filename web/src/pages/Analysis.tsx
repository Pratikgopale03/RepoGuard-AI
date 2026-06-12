import React, { useState } from 'react'

export default function Analysis(){
  const [repo, setRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const runAnalysis = async ()=>{
    if(!repo) return setError('Enter repository URL')
    setError(null)
    setLoading(true)
    try{
      const res = await fetch('/api/analyze', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ repo_url: repo }) })
      let data: any = {}
      try {
        data = await res.json()
      } catch (err) {
        const txt = await res.text().catch(() => '')
        data = txt ? { error: txt } : {}
      }
      if(!res.ok) throw new Error(data.error || 'Analysis failed')
      setResult(data)
    }catch(e:any){ setError(String(e)) }
    setLoading(false)
  }

  return (
    <div style={{minHeight:'60vh',padding:'24px 20px',color:'#e8f8ff'}}>
      <div style={{maxWidth:1180,margin:'0 auto'}}>
        <div style={{display:'flex',gap:12,alignItems:'center'}}>
          <input placeholder="Enter Repository URL" value={repo} onChange={e=>setRepo(e.target.value)} style={{flex:1,padding:12,borderRadius:10,border:'1px solid rgba(120,160,200,0.06)',background:'rgba(6,12,20,0.6)',color:'#e8f8ff'}} />
          <button onClick={runAnalysis} disabled={loading} style={{padding:'10px 18px',borderRadius:10,background:loading? 'rgba(120,160,200,0.2)':'linear-gradient(90deg,#7ee6c5,#9ed8ff)',border:'none'}}>{loading? 'Running...':'Analyze'}</button>
        </div>

        <div style={{marginTop:22,display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:16}}>
          {['Health Score','Bus Factor','Technical Debt','Security Score'].map((t,i)=>{
            const val = result?.summary && (i===0? result.summary.health_score : i===1? result.summary.bus_factor_percent : i===2? result.summary.technical_debt_hours : result.summary.security_score)
            return (
              <div key={t} style={{padding:16,borderRadius:12,background:'rgba(8,18,28,0.7)',border:'1px solid rgba(100,180,230,0.06)'}}>
                <div style={{fontSize:12,color:'#9ebfd6',marginBottom:8}}>{t}</div>
                <div style={{fontSize:20,fontWeight:700}}>{val ?? '--'}</div>
                <div style={{fontSize:12,color:'#88b6d0',marginTop:8}}>{val? 'Updated' : 'Awaiting analysis'}</div>
              </div>
            )
          })}
        </div>

        {error && <div style={{marginTop:12,color:'#ffb4b4'}}>{error}</div>}
      </div>
    </div>
  )
}
