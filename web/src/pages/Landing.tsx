import React, { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5174'

function parseJwt(token: string): any {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

export default function Landing(){
  const [jwt, setJwt] = useState<string | null>(localStorage.getItem('rg_jwt'))
  const [userPlan, setUserPlan] = useState<string>('free')
  const STREAMLIT_BASE = import.meta.env.VITE_STREAMLIT_BASE || 'http://localhost:8516'

  // Always read JWT fresh from localStorage at click-time — never use stale React state
  const getWorkspaceUrl = () => {
    const token = localStorage.getItem('rg_jwt')
    if (token && token !== 'null' && token.trim() !== '') {
      return `${STREAMLIT_BASE}/?token=${token}&view=analysis`
    }
    return `${STREAMLIT_BASE}/?view=analysis`
  }

  useEffect(() => {
    const current = localStorage.getItem('rg_jwt')
    if (current && current !== 'null') {
      setJwt(current)
      const decoded = parseJwt(current)
      if (decoded && decoded.plan) {
        setUserPlan(decoded.plan)
      }
      // Fetch latest plan from server
      fetch(`${API_BASE}/api/me`, {
        headers: { 'Authorization': `Bearer ${current}` }
      })
      .then(res => res.json())
      .then(data => {
        if (data && data.plan) {
          setUserPlan(data.plan)
        }
      })
      .catch(() => {})
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('rg_jwt')
    setJwt(null)
    window.location.reload()
  }

  // Navigate to workspace using fresh token from localStorage
  const goToWorkspace = (e: React.MouseEvent) => {
    e.preventDefault()
    window.location.href = getWorkspaceUrl()
  }

  return (
    <div>
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
            <a className="landing-header-link" href="/">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', verticalAlign: 'middle' }}>
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
              </svg>
              Home
            </a>
            {jwt ? (
              <>
                <a
                  className="landing-header-link"
                  href={getWorkspaceUrl()}
                  onClick={goToWorkspace}
                  style={{ cursor: 'pointer' }}
                >
                  Workspace
                </a>
                {userPlan === 'pro' && (
                  <span style={{
                    fontSize: '10px',
                    fontWeight: 900,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    padding: '3px 8px',
                    background: 'linear-gradient(90deg, #eab308, #c084fc)',
                    color: '#120a1c',
                    borderRadius: '99px',
                    marginRight: '12px',
                    boxShadow: '0 0 10px rgba(192,132,252,0.4)',
                    display: 'inline-flex',
                    alignItems: 'center'
                  }}>PRO</span>
                )}
                <a className="landing-header-link-premium" href="/pricing">Pricing</a>
                <button
                  onClick={handleLogout}
                  style={{
                    background: 'transparent',
                    border: '1px solid rgba(190,232,255,0.4)',
                    color: 'rgba(190,232,255,0.9)',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontSize: '0.95rem'
                  }}
                >
                  Log Out
                </button>
              </>
            ) : (
              <>
                <a className="landing-header-link" href="/login">Login</a>
                <a className="landing-header-link-premium" href="/pricing">Pricing</a>
                <a className="landing-header-btn" href="/login">Try for Free</a>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="landing-wrap">
        <div className="landing-left">
          <div className="landing-kicker">Engineering Visibility</div>
          <h1 className="landing-title">Repository Intelligence, Designed for Fast Decisions</h1>
          <p className="hero-sub">
            Measure health, security, ownership risk, and debt in one polished analysis surface.
          </p>
          {jwt ? (
            <a className="landing-cta" href={getWorkspaceUrl()} onClick={goToWorkspace}>Get Started</a>
          ) : (
            <a className="landing-cta" href="/login">Get Started</a>
          )}
        </div>
        <div className="landing-right">
          <div className="landing-image" />
        </div>
      </main>

      {/* Trust Banner */}
      <section className="landing-trust-bar">
        <p className="trust-title">TRUSTED BY FAST-GROWING ENGINEERING ORGANIZATIONS</p>
        <div className="trust-logos">
          <span className="trust-logo">⚡ Supabase</span>
          <span className="trust-logo">▲ Vercel</span>
          <span className="trust-logo">⬢ Node.js</span>
          <span className="trust-logo">🌀 Prisma</span>
        </div>
      </section>

      {/* Stats Section */}
      <section className="landing-stats-section">
        <div className="stats-grid">
          <div className="stat-card">
            <h3 className="stat-value">99.9%</h3>
            <p className="stat-label">Analysis Accuracy</p>
          </div>
          <div className="stat-card">
            <h3 className="stat-value">12M+</h3>
            <p className="stat-label">Commits Scanned</p>
          </div>
          <div className="stat-card">
            <h3 className="stat-value">&lt; 2m</h3>
            <p className="stat-label">Audit Turnaround</p>
          </div>
        </div>
      </section>

      {/* Features Showcase */}
      <section className="landing-features-section">
        <div className="features-header">
          <h2 className="features-kicker">Unified Visibility</h2>
          <h3 className="features-title">Everything you need to secure your codebase</h3>
        </div>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">🔍</div>
            <h4 className="feature-name">AI Debt Estimation</h4>
            <p className="feature-desc">Quantify code maintenance backlogs in realistic, evidence-based engineering hours.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🛡️</div>
            <h4 className="feature-name">Postural Security Auditing</h4>
            <p className="feature-desc">Instantly identify missing access controls, stale branch drifts, and secret leaks.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">👥</div>
            <h4 className="feature-name">Bus Factor Analysis</h4>
            <p className="feature-desc">Pinpoint critical key-contributor dependencies and prevent knowledge silos.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">📄</div>
            <h4 className="feature-name">Executive PDF Reports</h4>
            <p className="feature-desc">Generate board-ready analysis summaries and export historical repository insights.</p>
          </div>
        </div>
      </section>

      {/* Premium Footer */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <p className="footer-text">RepoGuard AI • Engineering transparency, powered by intelligence</p>
          <div className="footer-links">
            <a href="#" className="footer-link">Documentation</a>
            <a href="#" className="footer-link">GitHub</a>
            <a href="#" className="footer-link">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
