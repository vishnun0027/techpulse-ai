import { NavLink, Outlet } from 'react-router-dom';
import { supabase } from '../supabase';
import { LayoutDashboard, Settings, LogOut, Activity } from 'lucide-react';

export default function DashboardLayout({ session }) {
  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <div className="app-container">
      <nav className="navbar glass-panel" style={{ borderRadius: 0, borderTop: 0, borderLeft: 0, borderRight: 0, position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '3rem' }}>
          <div className="brand">
            <Activity size={24} color="var(--accent)" />
            TechPulse Pro
          </div>
          
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {session.user.email}
          </div>
          <button className="secondary" onClick={handleLogout} style={{ padding: '0.5rem 1rem' }}>
            <LogOut size={16} /> Disconnect
          </button>
        </div>
      </nav>

      <main className="main-content" style={{ margin: '0 auto', width: '100%', maxWidth: '1400px' }}>
        <Outlet />
      </main>
    </div>
  );
}
