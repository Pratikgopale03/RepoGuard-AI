import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './styles.css'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Analysis from './pages/Analysis'
import Pricing from './pages/Pricing'

function App(){
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing/>} />
        <Route path="/login" element={<Login/>} />
        <Route path="/pricing" element={<Pricing/>} />
        <Route path="/analysis" element={<Analysis/>} />
      </Routes>
    </BrowserRouter>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
