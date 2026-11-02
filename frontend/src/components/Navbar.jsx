import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { ShieldCheck, Upload, LayoutDashboard, FileText, Activity, LogOut, ScanSearch, ShoppingBag, CheckCheck, Store, Folder, CircleAlert } from 'lucide-react';
import './Navbar.css';
import { authApi, setAccessToken } from '../api/client';

export default function Navbar({ user }) {
  const [intake,setIntake]=useState(false),[open,setOpen]=useState(false);
  useEffect(()=>{const update=()=>setIntake(Boolean(document.querySelector('.intake-fullscreen-marker'))&&!document.querySelector('.cv-vendor-page'));const observer=new MutationObserver(update);observer.observe(document.body,{childList:true,subtree:true});update();return()=>observer.disconnect();},[]);
  useEffect(()=>{setOpen(false);document.body.classList.toggle('request-navigation-collapsed',intake);return()=>document.body.classList.remove('request-navigation-collapsed');},[intake]);
  const logout = async () => { try { await authApi.logout(); } finally { setAccessToken(null); window.dispatchEvent(new Event('auditai:session-expired')); } };
  const links = [['/', 'Overview', LayoutDashboard], ['/procurement/requests', 'Requests', ShoppingBag], ['/procurement/approvals', 'Approvals', CheckCheck], ['/procurement/exceptions', 'Exceptions', CircleAlert], ['/procurement/suppliers', 'Suppliers', Store], ['/procurement/documents', 'Documents', Folder]];
  return <>{intake&&<button type="button" className="request-menu-toggle" aria-label={open?'Close navigation':'Open navigation'} aria-expanded={open} onClick={()=>setOpen(!open)}>☰</button>}<nav className={`navbar ${intake?'request-navbar':''} ${open?'request-navbar-open':''}`} aria-label="Main navigation">
    <div className="navbar-brand"><ShieldCheck size={29}/><div><span className="brand-text">AuditAI</span><small>PROCUREMENT WORKSPACE</small></div></div>
    <div className="navbar-links">{links.map(([to, label, Icon]) => <NavLink key={to} end={to === '/'} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18}/><span>{label}</span></NavLink>)}</div>
    <div className="nav-section-label">AUDIT & INTELLIGENCE</div>
    <div className="navbar-links">{[['/expense-dashboard','Expense analytics',Activity],['/claims','Expense claims',FileText],['/upload','Data ingestion',Upload],['/control-points','Control points',ScanSearch],['/audit-screens','Audit screens',ShieldCheck]].map(([to,label,Icon]) => <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18}/><span>{label}</span></NavLink>)}</div>
    <div className="nav-profile"><span className="nav-avatar">{(user?.full_name || user?.email || 'A').slice(0,1).toUpperCase()}</span><div><strong>{user?.full_name || user?.email?.split('@')[0]}</strong><small>{user?.role || 'Requester'}</small></div><button onClick={logout} aria-label="Sign out"><LogOut size={17}/></button></div>
  </nav></>;
}
