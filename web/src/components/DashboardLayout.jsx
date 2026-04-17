import { NavLink, Outlet } from 'react-router-dom';
import { supabase } from '../supabase';
import { LayoutDashboard, Settings, LogOut, Activity } from 'lucide-react';

export default function DashboardLayout({ session }) {
  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <div className="app-container">
      <aside className="sidebar glass-panel" style={{ borderRadius: 0, borderTop: 0, borderBottom: 0, borderLeft: 0 }}>
        <div className="brand">
          <Activity size={24} color="var(--accent)" />
          TechPulse Pro
        </div>
        
        <div style={{ flex: 1, marginTop: '1rem' }}>
          <div className="nav-links">
            <NavLink 
              to="/" 
              end
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <LayoutDashboard size={18} /> Dashboard
            </NavLink>
            <NavLink 
              to="/settings" 
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Settings size={18} /> Settings
            </NavLink>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: '1.5rem' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem', wordBreak: 'break-all' }}>
            {session.user.email}
          </div>
          <button className="secondary" onClick={handleLogout} style={{ width: '100%', justifyContent: 'center' }}>
            <LogOut size={16} /> Disconnect
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
