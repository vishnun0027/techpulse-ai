import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { supabase } from './supabase';
import AuthView from './components/AuthView';
import DashboardLayout from './components/DashboardLayout';
import DashboardView from './components/DashboardView';
import SettingsView from './components/SettingsView';
import './index.css';

function App() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  if (!supabase) {
    return (
      <div className="auth-wrapper" style={{ flexDirection: 'column', gap: '1rem', textAlign: 'center' }}>
        <h1 style={{ color: '#ef4444' }}>Missing Credentials!</h1>
        <p>You forgot to configure your keys. Please create <code>web/.env</code> with your Supabase variables.</p>
      </div>
    );
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (loading) {
    return <div className="auth-wrapper">Loading TechPulse AI...</div>;
  }

  return (
    <Router>
      <Routes>
        <Route 
          path="/auth" 
          element={!session ? <AuthView /> : <Navigate to="/" />} 
        />
        <Route 
          path="/" 
          element={session ? <DashboardLayout session={session} /> : <Navigate to="/auth" />}
        >
          <Route index element={<DashboardView session={session} />} />
          <Route path="settings" element={<SettingsView session={session} />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
