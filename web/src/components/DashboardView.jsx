import { useState, useEffect } from 'react';
import { supabase } from '../supabase';
import { formatDistanceToNow } from 'date-fns';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DashboardView({ session }) {
  const [stats, setStats] = useState({ total: 0, delivered: 0, ready: 0 });
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      // Fetch counts
      const [{ count: total }, { count: delivered }, { count: ready }, { data: recent }] = await Promise.all([
        supabase.from('articles').select('source_url', { count: 'exact', head: true }),
        supabase.from('articles').select('source_url', { count: 'exact', head: true }).eq('is_delivered', true),
        supabase.from('articles').select('source_url', { count: 'exact', head: true }).eq('is_delivered', false).gte('score', 2.5),
        supabase.from('articles').select('*').order('created_at', { ascending: false }).limit(20)
      ]);

      setStats({ total: total || 0, delivered: delivered || 0, ready: ready || 0 });
      setArticles(recent || []);
      setLoading(false);
    }
    fetchData();
  }, [session]);

  const mockChartData = [
    { name: 'Mon', delivered: 12 },
    { name: 'Tue', delivered: 19 },
    { name: 'Wed', delivered: 15 },
    { name: 'Thu', delivered: 22 },
    { name: 'Fri', delivered: 28 },
    { name: 'Sat', delivered: 10 },
    { name: 'Sun', delivered: 34 }
  ];

  return (
    <div>
      <div className="header">
        <h1>Overview</h1>
      </div>

      <div className="metrics-grid">
        <div className="metric-card glass-panel">
          <div className="metric-label">Total Articles Scored</div>
          <div className="metric-value">{loading ? '...' : stats.total}</div>
        </div>
        <div className="metric-card glass-panel">
          <div className="metric-label">Successfully Delivered</div>
          <div className="metric-value" style={{ color: '#10b981' }}>{loading ? '...' : stats.delivered}</div>
        </div>
        <div className="metric-card glass-panel">
          <div className="metric-label">High-Score Pending</div>
          <div className="metric-value" style={{ color: '#f59e0b' }}>{loading ? '...' : stats.ready}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1.5rem', fontWeight: 600 }}>Delivery Velocity</h2>
          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer>
              <AreaChart data={mockChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Area type="monotone" dataKey="delivered" stroke="#3b82f6" fill="rgba(59, 130, 246, 0.2)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--card-border)' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Recent Intelligence</h2>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Discovered</th>
                <th>Source</th>
                <th>Title</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {articles.map((a) => (
                <tr key={a.source_url}>
                  <td style={{ whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                    {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                  </td>
                  <td>{a.source}</td>
                  <td style={{ maxWidth: '400px' }}>
                    <a href={a.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                      {a.title}
                    </a>
                  </td>
                  <td>
                    <span style={{ 
                      padding: '0.25rem 0.5rem', 
                      borderRadius: '4px', 
                      background: a.score >= 4 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255,255,255,0.05)',
                      color: a.score >= 4 ? '#10b981' : 'inherit'
                    }}>
                      {a.score.toFixed(1)}
                    </span>
                  </td>
                  <td>
                    {a.is_delivered ? 
                      <span style={{ color: '#10b981', fontSize: '0.875rem' }}>Delivered</span> : 
                      <span style={{ color: '#f59e0b', fontSize: '0.875rem' }}>Pending</span>
                    }
                  </td>
                </tr>
              ))}
              {articles.length === 0 && !loading && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                    No intelligence gathered yet. Add some RSS sources!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
