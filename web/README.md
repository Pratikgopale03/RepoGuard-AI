Quick dev instructions

1. Install dependencies

```bash
cd web
npm install
```

2. Start API server (auth endpoints)

```bash
npm run api
# by default listens on http://localhost:5174
```

3. Start frontend

```bash
npm run dev
# Vite default http://localhost:5173
```

4. Open http://localhost:5173 and visit /login

Notes:
- This is a demo auth server that persists users to `web/.users.json` (file in the `web` folder parent). It's suitable for local testing only.
- Set `REPOGUARD_JWT_SECRET` env var before running the API to change token secret.
