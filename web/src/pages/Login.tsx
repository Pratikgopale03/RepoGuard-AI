import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
// We'll use the backend API instead of localStorage for auth
// Default to the local Node auth server started by `npm run api`.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5174';

export default function Login(){
  const [tab, setTab] = useState<'login'|'register'>('login')
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const nav = useNavigate()
  // Keep login/register flow pinned to the free app.
  const STREAMLIT_LOGIN_BASE = import.meta.env.VITE_STREAMLIT_LOGIN_BASE || 'http://localhost:8516'

  React.useEffect(() => {
    // Check for OAuth token in URL
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token');
    const urlError = params.get('error');

    if (urlToken) {
      localStorage.setItem('rg_jwt', urlToken);
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
      redirectToFreeAnalysis(urlToken);
      return;
    }

    if (urlError) {
      setMsg(`GitHub login failed: ${urlError}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    const token = localStorage.getItem('rg_jwt')
    if (token) {
      redirectToFreeAnalysis(token)
    }
  }, [])

  const redirectToFreeAnalysis = (token: string) => {
    try {
      const u = new URL(STREAMLIT_LOGIN_BASE)
      u.searchParams.set('token', token)
      u.searchParams.set('view', 'analysis')
      window.location.href = u.toString()
    } catch (_) {
      window.location.href = `${STREAMLIT_LOGIN_BASE.replace(/\/+$/,'')}/?token=${encodeURIComponent(token)}&view=analysis`
    }
  }

  const handleRegister = async(e:any)=>{
    e.preventDefault()
    setMsg(null)
    const em = email.trim().toLowerCase()
    if(!em || !em.includes('@')){ setMsg('Invalid email'); return }
    if(pw.length < 6){ setMsg('Password must be at least 6 chars'); return }
    if(pw !== pw2){ setMsg('Passwords do not match'); return }
    try{
      const res = await fetch(`${API_BASE}/api/register`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ email: em, password: pw })
      })
      let data: any = {}
      try {
        data = await res.json()
      } catch (e) {
        const txt = await res.text().catch(() => '')
        data = txt ? { error: txt } : {}
      }
      if(!res.ok){ setMsg(data.error || 'Registration failed'); return }
      if (data.token) localStorage.setItem('rg_jwt', data.token)
      setMsg('Account created — signed in')
      // Request a short-lived Streamlit token and open Streamlit analysis.
      // If that fails, fall back to opening Streamlit with the primary JWT.
      try {
        const stRes = await fetch(`${API_BASE}/api/streamlit-token`, { method: 'POST', headers: { 'Authorization': `Bearer ${data.token}`, 'Content-Type':'application/json' }, body: JSON.stringify({}) })
        let stData:any = {}
        try { stData = await stRes.json() } catch(_) { stData = {} }
        if (stRes.ok && stData.token) {
          redirectToFreeAnalysis(stData.token)
          return
        }
        // fallback: open Streamlit with the original JWT if short-lived token not available
        redirectToFreeAnalysis(data.token)
        return
      } catch(err:any){
        // if anything goes wrong, navigate to the React analysis page as an ultimate fallback
        setMsg('Token redirect failed, opening in-app analysis')
        setTimeout(()=>nav('/analysis'),600)
      }
    }catch(err:any){ setMsg(String(err)) }
  }

  const handleLogin = async(e:any)=>{
    e.preventDefault()
    setMsg(null)
    const em = email.trim().toLowerCase()
    try{
      const res = await fetch(`${API_BASE}/api/login`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ email: em, password: pw })
      })
      let data: any = {}
      try {
        data = await res.json()
      } catch (e) {
        const txt = await res.text().catch(() => '')
        data = txt ? { error: txt } : {}
      }
      if(!res.ok){ setMsg(data.error || 'Login failed'); return }
      if (data.token) localStorage.setItem('rg_jwt', data.token)
      setMsg('Welcome back')
      // Try to get Streamlit token and open Streamlit analysis; fallback to primary JWT
      try {
        const stRes = await fetch(`${API_BASE}/api/streamlit-token`, { method: 'POST', headers: { 'Authorization': `Bearer ${data.token}`, 'Content-Type':'application/json' }, body: JSON.stringify({}) })
        let stData:any = {}
        try { stData = await stRes.json() } catch(_) { stData = {} }
        if (stRes.ok && stData.token) {
          redirectToFreeAnalysis(stData.token)
          return
        }
        redirectToFreeAnalysis(data.token)
        return
      } catch(err:any){
        setMsg('Token redirect failed, opening in-app analysis')
        setTimeout(()=>nav('/analysis'),400)
      }
    }catch(err:any){ setMsg(String(err)) }
  }

  return (
    <div className="page-login">
      <header className="landing-header">
        <div className="landing-header-inner">
          <a className="landing-header-brand" href="/">
            <svg className="landing-header-logo" viewBox="0 0 24 24" width="26" height="26" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 2Z" stroke="url(#brand-logo-gradient)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M12 6V18" stroke="url(#brand-logo-gradient)" strokeWidth="2" strokeDasharray="3 3" />
              <path d="M8 12H16" stroke="url(#brand-logo-gradient)" strokeWidth="2.5" strokeLinecap="round" />
              <defs>
                <linearGradient id="brand-logo-gradient" x1="3" y1="2" x2="21" y2="23" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#4ce3c1" />
                  <stop offset="0.5" stopColor="#7dd3fc" />
                  <stop offset="1" stopColor="#8b5cf6" />
                </linearGradient>
              </defs>
            </svg>
            <span>RepoGuard</span>
          </a>
          <div className="landing-header-nav">
            <a className="landing-header-link" href="/"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle' }}><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>Home</a>
            <a className="landing-header-link-premium" href="/pricing">Pricing</a>
          </div>
        </div>
      </header>

      <main className="login-shell">
        <div className="login-hero">
          <h1>Welcome back to RepoGuard</h1>
          <p className="hero-sub">Log in to run analyses, view history, and download reports.</p>
        </div>

        <div className="login-panel">
          <div className="login-card">
          <div className="tabs">
            <button className={tab==='login'? 'active':''} onClick={()=>{setTab('login'); setMsg(null)}}>Log In</button>
            <button className={tab==='register'? 'active':''} onClick={()=>{setTab('register'); setMsg(null)}}>Register</button>
          </div>

          {msg && <div className="form-msg">{msg}</div>}

          {tab==='login' ? (
            <form onSubmit={handleLogin}>
              <label>Email</label>
              <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" />
              <label>Password</label>
              <input type="password" value={pw} onChange={e=>setPw(e.target.value)} />
              <button className="primary" type="submit">Log In</button>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              <label>Email</label>
              <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com" />
              <label>Password</label>
              <input type="password" value={pw} onChange={e=>setPw(e.target.value)} />
              <label>Confirm Password</label>
              <input type="password" value={pw2} onChange={e=>setPw2(e.target.value)} />
              <button className="primary" type="submit">Create Account</button>
            </form>
          )}

          <div className="oauth-divider" style={{ display: 'flex', alignItems: 'center', margin: '20px 0', color: '#64748b', fontSize: '14px' }}>
            <div style={{ flex: 1, height: '1px', background: '#334155' }}></div>
            <span style={{ padding: '0 10px' }}>or</span>
            <div style={{ flex: 1, height: '1px', background: '#334155' }}></div>
          </div>
          
          <button 
            type="button" 
            className="oauth-btn github" 
            onClick={() => window.location.href = `${API_BASE}/api/auth/github`}
            style={{ 
              width: '100%', padding: '12px', display: 'flex', alignItems: 'center', 
              justifyContent: 'center', gap: '10px', background: '#1e293b', 
              color: 'white', border: '1px solid #334155', borderRadius: '8px',
              cursor: 'pointer', fontSize: '15px', fontWeight: '500', transition: 'all 0.2s'
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = '#0f172a')}
            onMouseOut={(e) => (e.currentTarget.style.background = '#1e293b')}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            Continue with GitHub
          </button>
          </div>
          <div className="login-aside">
            <div className="aside-title">Enterprise-Grade Insights</div>
            <div className="aside-subtitle">RepoGuard AI analyzes metadata, code quality, and contributor activity to deliver complete engineering visibility.</div>
            
            <div className="aside-features">
              <div className="aside-feature">
                <div className="aside-feature-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                </div>
                <div className="aside-feature-text">
                  <h4>Technical Debt Estimator</h4>
                  <p>Quantify maintenance backlogs in realistic engineering hours.</p>
                </div>
              </div>

              <div className="aside-feature">
                <div className="aside-feature-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                </div>
                <div className="aside-feature-text">
                  <h4>Postural Security Auditing</h4>
                  <p>Catch missing controls and stale branch vulnerabilities in seconds.</p>
                </div>
              </div>

              <div className="aside-feature">
                <div className="aside-feature-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                </div>
                <div className="aside-feature-text">
                  <h4>Bus Factor Resilience</h4>
                  <p>Identify knowledge concentration silos and key-contributor risks.</p>
                </div>
              </div>
            </div>

            <div className="aside-footer-badge">
              <span className="badge-glow"></span>
              <span>⚡ Powered by LLaMA 3.3 70B</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
