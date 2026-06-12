const express = require('express');
const fs = require('fs');
const path = require('path');
const bcrypt = require('bcryptjs');
const jwt = require('jwt-simple');
const cors = require('cors');
const Razorpay = require('razorpay');

const dotenvResult = require('dotenv').config({
  path: path.resolve(__dirname, '.env'),
  override: true
});
if (dotenvResult.error) {
  console.warn('dotenv load failed:', dotenvResult.error.message);
}

const app = express();
app.use(cors());
app.use(express.json());

const USERS_FILE = path.join(__dirname, '..', '..', '.users.json');
const JWT_SECRET = process.env.REPOGUARD_JWT_SECRET || 'repoguard_dev_secret_change_me';
const RAZORPAY_KEY_ID = process.env.RAZORPAY_KEY_ID || '';
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';

const razorpay = RAZORPAY_KEY_ID && RAZORPAY_KEY_SECRET
  ? new Razorpay({ key_id: RAZORPAY_KEY_ID, key_secret: RAZORPAY_KEY_SECRET })
  : null;

function loadUsers(){
  try{ return JSON.parse(fs.readFileSync(USERS_FILE,'utf8')) }catch(e){ return {} }
}
function saveUsers(u){ fs.writeFileSync(USERS_FILE, JSON.stringify(u, null, 2)) }

function getAuthPayload(req, res){
  const auth = req.headers.authorization || '';
  const m = auth.match(/^Bearer\s+(.*)$/i);
  if(!m) {
    res.status(401).json({ error: 'Missing token' });
    return null;
  }
  try {
    return jwt.decode(m[1], JWT_SECRET);
  } catch(e){
    res.status(401).json({ error: 'Invalid token' });
    return null;
  }
}

app.post('/api/register', async (req, res) => {
  const { email, password } = req.body || {};
  if(!email || !email.includes('@')) return res.status(400).json({ error: 'Invalid email' });
  if(!password || password.length < 6) return res.status(400).json({ error: 'Password must be 6+ chars' });
  const em = email.trim().toLowerCase();
  const users = loadUsers();
  if(users[em]) return res.status(409).json({ error: 'Account exists' });
  const hash = await bcrypt.hash(password, 10);
  users[em] = { email: em, password_hash: hash, plan: 'free' };
  saveUsers(users);
  const token = jwt.encode({ sub: em, plan: 'free', iat: Date.now() }, JWT_SECRET);
  res.json({ token });
});

app.post('/api/login', async (req, res) => {
  const { email, password } = req.body || {};
  const em = (email || '').trim().toLowerCase();
  const users = loadUsers();
  const u = users[em];
  if(!u) return res.status(404).json({ error: 'No account found' });
  const ok = await bcrypt.compare(password, u.password_hash);
  if(!ok) return res.status(401).json({ error: 'Incorrect password' });
  const token = jwt.encode({ sub: em, plan: u.plan || 'free', iat: Date.now() }, JWT_SECRET);
  res.json({ token });
});

// --- GitHub OAuth ---
app.get('/api/auth/github', (req, res) => {
  const clientId = process.env.GITHUB_CLIENT_ID;
  if (!clientId) return res.status(500).send('GitHub OAuth not configured');
  const url = `https://github.com/login/oauth/authorize?client_id=${clientId}&scope=user:email`;
  res.redirect(url);
});

app.get('/api/auth/github/callback', async (req, res) => {
  const { code } = req.query;
  if (!code) return res.status(400).send('No code provided');

  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;
  const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:5173';

  try {
    // 1. Exchange code for access token
    const tokenRes = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        code
      })
    });
    const tokenData = await tokenRes.json();
    const accessToken = tokenData.access_token;

    if (!accessToken) {
      console.error('GitHub token error:', tokenData);
      return res.redirect(`${frontendUrl}/login?error=oauth_failed`);
    }

    // 2. Fetch user's emails
    const emailsRes = await fetch('https://api.github.com/user/emails', {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'User-Agent': 'RepoGuard-AI-App'
      }
    });
    const emails = await emailsRes.json();
    const primaryEmailObj = emails.find(e => e.primary) || emails[0];
    
    if (!primaryEmailObj || !primaryEmailObj.email) {
      return res.redirect(`${frontendUrl}/login?error=no_email`);
    }

    const email = primaryEmailObj.email.toLowerCase();

    // 3. Find or create user
    const users = loadUsers();
    if (!users[email]) {
      // Create a new user with a dummy password hash since they use OAuth
      const dummyHash = await bcrypt.hash(Math.random().toString(36), 10);
      users[email] = { email, password_hash: dummyHash, plan: 'free' };
      saveUsers(users);
    }

    // 4. Generate JWT (Streamlit requires timestamps in seconds)
    const plan = users[email].plan || 'free';
    const now = Math.floor(Date.now() / 1000);
    const token = jwt.encode({ 
      sub: email, 
      plan, 
      iat: now, 
      exp: now + 60 * 60 * 24 * 7 // 7 days expiry
    }, JWT_SECRET);

    // 5. Redirect back to frontend
    res.redirect(`${frontendUrl}/login?token=${token}`);
  } catch (err) {
    console.error('GitHub OAuth error:', err);
    res.redirect(`${process.env.FRONTEND_URL || 'http://localhost:5173'}/login?error=oauth_exception`);
  }
});

// Mock analysis endpoint (fast prototype)
app.post('/api/analyze', async (req, res) => {
  const { repo_url } = req.body || {}
  if(!repo_url) return res.status(400).json({ error: 'Missing repo_url' })
  // For speed, return mocked analysis results
  const sample = {
    repository: repo_url,
    summary: {
      health_score: 82,
      bus_factor_percent: 64,
      technical_debt_hours: 120,
      security_score: 78
    },
    charts: {
      language_distribution: { JavaScript: 58, TypeScript: 28, Other: 14 },
      contributors: [{name:'alice',commits:120},{name:'bob',commits:80}]
    }
  }
  // simulate short processing time
  setTimeout(() => res.json(sample), 600)
})

app.get('/api/me', (req, res) => {
  const auth = req.headers.authorization || '';
  const m = auth.match(/^Bearer\s+(.*)$/i);
  if(!m) return res.status(401).json({ error: 'Missing token' });
  const token = m[1];
  try{
    const payload = jwt.decode(token, JWT_SECRET);
    res.json({ user: payload.sub, plan: payload.plan });
  }catch(e){ res.status(401).json({ error: 'Invalid token' }); }
});

// Issue a short-lived token that Streamlit can consume for bootstrapping a session
app.post('/api/streamlit-token', (req, res) => {
  const payload = getAuthPayload(req, res);
  if(!payload) return;
  try{
    const now = Math.floor(Date.now() / 1000);
    // longer expiry (7 days) to avoid frequent re-login
    const stPayload = { sub: payload.sub, plan: payload.plan, iat: now, exp: now + 60 * 60 * 24 * 7 };
    const stoken = jwt.encode(stPayload, JWT_SECRET);
    res.json({ token: stoken });
  }catch(e){ res.status(401).json({ error: 'Invalid token' }); }
});

app.post('/api/upgrade-plan', (req, res) => {
  const payload = getAuthPayload(req, res);
  if(!payload) return;
  const users = loadUsers();
  const email = (payload.sub || '').toLowerCase();
  if(!email) return res.status(400).json({ error: 'Invalid payload' });
  if(!users[email]) {
    users[email] = { email, password_hash: '', plan: 'pro' };
  } else {
    users[email].plan = 'pro';
  }
  saveUsers(users);
  const now = Math.floor(Date.now() / 1000);
  const token = jwt.encode({ sub: email, plan: 'pro', iat: now, exp: now + 60*60*24*7 }, JWT_SECRET);
  res.json({ token, plan: 'pro' });
});

app.get('/api/razorpay-key', (req, res) => {
  if (!RAZORPAY_KEY_ID) return res.status(500).json({ error: 'Razorpay key not configured' });
  res.json({ key_id: RAZORPAY_KEY_ID });
});

app.post('/api/razorpay-order', async (req, res) => {
  if (!razorpay) return res.status(500).json({ error: 'Razorpay not configured' });
  const { plan } = req.body || {};
  const planKey = (plan || '').toLowerCase();

  const planPricing = {
    pro: { amount: 49900, currency: 'INR', label: 'RepoGuard Pro (Monthly)' },
  };

  const selected = planPricing[planKey];
  if (!selected) return res.status(400).json({ error: 'Invalid plan' });

  try {
    const order = await razorpay.orders.create({
      amount: selected.amount,
      currency: selected.currency,
      receipt: `rg_${Date.now()}`,
      notes: { plan: planKey, label: selected.label }
    });
    res.json({ order_id: order.id, amount: selected.amount, currency: selected.currency, label: selected.label });
  } catch (err) {
    res.status(500).json({ error: 'Failed to create Razorpay order' });
  }
});

const port = process.env.PORT || 5174;
app.listen(port, () => console.log('Auth API running on port', port));
