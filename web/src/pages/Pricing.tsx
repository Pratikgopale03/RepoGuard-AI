import React, { useEffect, useState } from 'react'

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

export default function Pricing(){
  const [keyId, setKeyId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [jwt, setJwt] = useState<string | null>(localStorage.getItem('rg_jwt'))
  const [userPlan, setUserPlan] = useState<string>('free')

  useEffect(() => {
    // Extract token from query parameters if present
    const params = new URLSearchParams(window.location.search)
    const tokenFromUrl = params.get('token')
    let currentToken = tokenFromUrl || localStorage.getItem('rg_jwt')

    if (tokenFromUrl) {
      localStorage.setItem('rg_jwt', tokenFromUrl)
      setJwt(tokenFromUrl)
      // Clean the query parameter from the URL bar without refreshing
      window.history.replaceState({}, document.title, window.location.pathname)
    }

    if (currentToken) {
      setLoading(false)
      const decoded = parseJwt(currentToken)
      if (decoded && decoded.plan) {
        setUserPlan(decoded.plan)
      }
      
      // Fetch latest plan from server
      fetch(`${API_BASE}/api/me`, {
        headers: { 'Authorization': `Bearer ${currentToken}` }
      })
      .then(res => res.json())
      .then(data => {
        if (data && data.plan) {
          setUserPlan(data.plan)
        }
      })
      .catch(() => {})
    }

    const loadKey = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/razorpay-key`)
        const data = await res.json()
        if (res.ok && data.key_id) setKeyId(data.key_id)
        else setError(data.error || 'Razorpay key not available')
      } catch (err:any) {
        setError(String(err))
      }
    }
    loadKey()
  }, [])

  const loadScript = () => new Promise<boolean>((resolve) => {
    const existing = document.getElementById('razorpay-checkout')
    if (existing) return resolve(true)
    const script = document.createElement('script')
    script.id = 'razorpay-checkout'
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => resolve(false)
    document.body.appendChild(script)
  })

  const startCheckout = async () => {
    setError(null)
    setLoading(true)
    const jwt = localStorage.getItem('rg_jwt')
    if (!jwt) {
      setLoading(false)
      setError('Please sign in before upgrading to Pro.')
      window.location.href = '/login'
      return
    }
    const ok = await loadScript()
    if (!ok) {
      setLoading(false)
      setError('Failed to load Razorpay checkout')
      return
    }
    if (!keyId) {
      setLoading(false)
      setError('Razorpay key not available')
      return
    }
    try {
      const orderRes = await fetch(`${API_BASE}/api/razorpay-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: 'pro' })
      })
      const order = await orderRes.json()
      if (!orderRes.ok) throw new Error(order.error || 'Order creation failed')

      const STREAMLIT_BASE = import.meta.env.VITE_STREAMLIT_BASE || 'http://localhost:8516'
      const STREAMLIT_PRO_BASE = import.meta.env.VITE_STREAMLIT_PRO_BASE || STREAMLIT_BASE
      const rzp = new (window as any).Razorpay({
        key: keyId,
        amount: order.amount,
        currency: order.currency,
        name: 'RepoGuard AI',
        description: order.label,
        order_id: order.order_id,
        handler: async () => {
          // On successful payment, attempt to upgrade the account server-side.
          try {
            const jwtNow = localStorage.getItem('rg_jwt')
            if (jwtNow) {
              const upgradeRes = await fetch(`${API_BASE}/api/upgrade-plan`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${jwtNow}` }
              })
              const upgrade = await upgradeRes.json()
              if (upgradeRes.ok && upgrade.token) {
                localStorage.setItem('rg_jwt', upgrade.token)
              }
            }
          } catch (_){}
          const finalJwt = localStorage.getItem('rg_jwt')
          try {
            const redirectUrl = new URL(STREAMLIT_PRO_BASE)
            redirectUrl.searchParams.set('view', 'analysis')
            if (finalJwt) redirectUrl.searchParams.set('token', finalJwt)
            window.location.href = redirectUrl.toString()
          } catch (e) {
            const tokenParam = finalJwt ? `&token=${encodeURIComponent(finalJwt)}` : ''
            window.location.href = `${STREAMLIT_BASE.replace(/\/+$/,'')}/?view=analysis${tokenParam}`
          }
        },
        theme: { color: '#00c2a8' }
      })
      rzp.open()
    } catch (err:any) {
      setError(String(err))
    }
    setLoading(false)
  }

  const STREAMLIT_BASE = import.meta.env.VITE_STREAMLIT_BASE || 'http://localhost:8516'
  const workspaceUrl = `${STREAMLIT_BASE}/?token=${jwt}&view=analysis`

  const handleLogout = () => {
    localStorage.removeItem('rg_jwt')
    setJwt(null)
    window.location.reload()
  }

  return (
    <div className="pricing-shell">
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
            {jwt ? (
              <>
                <a className="landing-header-link" href={workspaceUrl}>Workspace</a>
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
                <a className="landing-header-btn" href="/login">Try for Free</a>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="pricing-hero">
        <div className="pricing-hero-inner">
          <div className="pricing-kicker">Pricing</div>
          <h1 className="pricing-title">Plans that scale with your engineering team</h1>
          <p className="pricing-sub">
            Start free and upgrade when you need deeper analysis history, higher limits, and priority AI runs.
          </p>
        </div>
      </main>

      <section className="pricing-grid">
        <article className="pricing-card">
          <div className="pricing-tag">Free</div>
          <div className="pricing-price">Rs 0 <span>/ month</span></div>
          <ul className="pricing-list">
            <li>Daily analysis limits</li>
            <li>Core health + risk metrics</li>
            <li>Basic charts and exports</li>
          </ul>
          <a className="pricing-cta" href="/login">Get Started</a>
        </article>

        <article className="pricing-card pricing-card--pro">
          <div className="pricing-tag">Pro</div>
          <div className="pricing-price">Rs 499 <span>/ month</span></div>
          <ul className="pricing-list">
            <li>Higher daily analysis limits</li>
            <li>Full AI insights + reports</li>
            <li>Priority processing</li>
          </ul>
          { userPlan === 'pro' ? (
            <button className="pricing-cta pricing-cta--pay" disabled style={{ background: 'linear-gradient(90deg, #10b981, #059669)', border: 'none', color: '#fff', cursor: 'default', opacity: 1 }}>
              ✓ Current Active Plan
            </button>
          ) : !localStorage.getItem('rg_jwt') ? (
            <div>
              <a className="pricing-cta" href="/login">Sign in to upgrade</a>
            </div>
          ) : (
            <button className="pricing-cta pricing-cta--pay" onClick={startCheckout} disabled={loading || !keyId}>
              {loading ? 'Opening Razorpay...' : 'Upgrade to Pro'}
            </button>
          )}
          {userPlan !== 'pro' && !keyId && <div className="pricing-note">Razorpay not configured yet.</div>}
        </article>
      </section>

      {error && <div className="pricing-error">{error}</div>}
    </div>
  )
}
