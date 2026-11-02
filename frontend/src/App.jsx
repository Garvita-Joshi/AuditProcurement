import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Procurement from './pages/Procurement';
import Upload from './pages/Upload';
import ClaimsTable from './pages/ClaimsTable';
import ClaimDetail from './pages/ClaimDetail';
import AuditScreens from './pages/AuditScreens';
import ControlPoints from './pages/ControlPoints';
import Login from './pages/Login';
import { authApi, setAccessToken } from './api/client';

export default function App() {
  const [auth, setAuth] = useState({ checked: false, user: null });
  useEffect(() => {
    authApi.refresh().then(({ data }) => { setAccessToken(data.access_token); setAuth({ checked: true, user: data.user }); })
      .catch(() => setAuth({ checked: true, user: null }));
    const expire = () => setAuth({ checked: true, user: null });
    window.addEventListener('auditai:session-expired', expire);
    return () => window.removeEventListener('auditai:session-expired', expire);
  }, []);
  if (!auth.checked) return null;
  if (!auth.user) return <Login onAuthenticated={(data) => { setAccessToken(data.access_token); setAuth({ checked: true, user: data.user }); }} />;
  return <BrowserRouter><div className="app-container"><Navbar user={auth.user} /><Routes>
    <Route path="/sourcing" element={<Navigate to="/" replace />} /><Route path="/" element={<Procurement user={auth.user} />} /><Route path="/procurement/*" element={<Procurement user={auth.user} />} /><Route path="/expense-dashboard" element={<Dashboard />} /><Route path="/upload" element={<Upload />} />
    <Route path="/claims" element={<ClaimsTable />} /><Route path="/claims/:id" element={<ClaimDetail />} />
    <Route path="/audit-screens" element={<AuditScreens />} /><Route path="/control-points" element={<ControlPoints />} />
  </Routes></div></BrowserRouter>;
}
