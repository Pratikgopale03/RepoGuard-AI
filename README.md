# 🛡️ RepoGuard AI

**Full-Stack AI SaaS Platform**  
*React.js, Node.js, Python, Streamlit, Groq (LLaMA 3.3 70B), GitHub API, OAuth, Razorpay*

RepoGuard AI is an advanced, microservices-based SaaS application that autonomously analyzes GitHub repositories using Large Language Models to calculate real-world engineering metrics.

---

## 🚀 Key Features

* **AI-Powered Code Intelligence:** Integrated Meta's **LLaMA 3.3 70B** model to autonomously analyze repository metadata, generating complex engineering metrics like Technical Debt, Security Risk, and Bus Factor.
* **Streamlit Data Dashboards:** Built a highly interactive, Python-based analytics workspace using **Streamlit** to visualize AI insights, repository health scores, and contributor distributions in real-time.
* **GitHub REST API Integration:** Engineered dynamic data-ingestion pipelines to fetch live repository statistics, commit histories, and code structures for immediate analysis.
* **OAuth 2.0 Integration:** Implemented seamless "Sign in with GitHub" functionality to provide a frictionless, secure authentication experience for developers.
* **Razorpay Monetization:** Developed a complete subscription workflow with **Razorpay**, enforcing API token limits and granting premium workspace access to Pro-tier users.
* **Fault-Tolerant Architecture:** Built highly resilient data pipelines by implementing exponential backoff and intelligent mathematical fallbacks, ensuring 100% application uptime during upstream LLM rate limits (HTTP 429 errors).

---

## 🛠️ Technology Stack

### **Frontend (Client-Side)**
* **React.js** (via Vite): High-performance UI framework.
* **TypeScript / JavaScript:** Core programming languages.
* **Vanilla CSS:** Premium glassmorphism and modern UI styling.

### **Backend (API & Authentication)**
* **Node.js & Express.js:** Central API server handling registrations, payments, and OAuth.
* **JWT (JSON Web Tokens):** Stateless, secure cross-service authentication.
* **bcryptjs:** Secure local credential management.

### **AI Engine & Data Processing**
* **Python 3:** Core language for the analysis engine.
* **Streamlit:** Framework for building the data-heavy analysis dashboard.
* **Groq API & LLaMA 3.3 70B:** Ultra-fast AI inference engine and Large Language Model.

### **Database & Integrations**
* **SQLite:** Relational database for storing analysis history (`repoguard.db`).
* **Razorpay:** Payment gateway for Pro-tier subscriptions.

---

## ⚙️ Running Locally

### 1. Backend API (Node.js)
```bash
cd web
npm install
npm run api
```
*(Runs on port 5174)*

### 2. Frontend React App
```bash
cd web
npm run dev
```
*(Runs on port 5173)*

### 3. Streamlit Workspace Servers
```bash
# Terminal 1 (Free App)
python -m streamlit run app_free.py --server.port 8516

# Terminal 2 (Pro App)
python -m streamlit run app_pro.py --server.port 8517
```

---
*Note: This repository contains the full source code for the RepoGuard application, showcasing advanced integration of AI models with modern web development frameworks.*
