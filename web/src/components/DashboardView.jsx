import { useState, useEffect } from 'react';
import { supabase } from '../supabase';
import { formatDistanceToNow } from 'date-fns';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DashboardView({ session }) {
  const [stats, setStats] = useState({ total: 0, delivered: 0, ready: 0 });
  const [articles, setArticles] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      // Setup date bounds for chart
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 6);
      sevenDaysAgo.setHours(0, 0, 0, 0);

      // Fetch counts and recent items
      const [
        { count: total }, 
        { count: delivered }, 
        { count: ready }, 
        { data: recent }, 
        { data: chartArticles }
      ] = await Promise.all([
        supabase.from('articles').select('source_url', { count: 'exact', head: true }),
        supabase.from('articles').select('source_url', { count: 'exact', head: true }).eq('is_delivered', true),
        supabase.from('articles').select('source_url', { count: 'exact', head: true }).eq('is_delivered', false).gte('score', 2.5),
        supabase.from('articles').select('*').order('created_at', { ascending: false }).limit(20),
        supabase.from('articles').select('created_at').eq('is_delivered', true).gte('created_at', sevenDaysAgo.toISOString())
      ]);

      setStats({ total: total || 0, delivered: delivered || 0, ready: ready || 0 });
      setArticles(recent || []);

      // Build chart data
      const deliveryCounts = {};
      const today = new Date();
      for (let i = 6; i >= 0; i--) {
        const d = new Date(today);
        d.setDate(today.getDate() - i);
        const dayStr = d.toLocaleDateString('en-US', { weekday: 'short' });
        deliveryCounts[dayStr] = 0;
      }

      (chartArticles || []).forEach(a => {
        const d = new Date(a.created_at);
        const dayStr = d.toLocaleDateString('en-US', { weekday: 'short' });
        if (deliveryCounts[dayStr] !== undefined) {
          deliveryCounts[dayStr]++;
        }
      });

      setChartData(Object.keys(deliveryCounts).map(k => ({ name: k, delivered: deliveryCounts[k] })));
      setLoading(false);
    }
    fetchData();
  }, [session]);



  return (
    <div>
      <div className="header">
        <h1>Overview</h1>
      </div>

      <div className="metrics-grid">
        <div className="metric-card glass-panel hoverable">
          <div className="metric-label">Total Articles Scored</div>
          <div className="metric-value">{loading ? '...' : stats.total}</div>
        </div>
        <div className="metric-card glass-panel hoverable">
          <div className="metric-label">Successfully Delivered</div>
          <div className="metric-value" style={{ color: 'var(--semantic-success)' }}>{loading ? '...' : stats.delivered}</div>
        </div>
        <div className="metric-card glass-panel hoverable">
          <div className="metric-label">High-Score Pending</div>
          <div className="metric-value" style={{ color: 'var(--semantic-warning)' }}>{loading ? '...' : stats.ready}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Delivery Velocity</h2>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.05)', padding: '0.4rem 0.8rem', borderRadius: '6px' }}>
              Last 7 Days ▾
            </div>
          </div>
          <div style={{ height: '300px', width: '100%', position: 'relative' }}>
            {/* Subtle glow behind chart */}
            <div style={{ position: 'absolute', top: '10%', left: '10%', right: '10%', bottom: '10%', background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)', filter: 'blur(40px)', zIndex: 0, pointerEvents: 'none' }} />
            
            <ResponsiveContainer zIndex={1}>
              <AreaChart data={chartData}>
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
                    <a href={a.source_url} target="_blank" rel="noreferrer" className="article-title-link">
                      {a.title}
                    </a>
                  </td>
                  <td>
                    <span className={`badge ${a.score >= 4 ? 'success' : 'info'}`}>
                      ⭐ {a.score.toFixed(1)}
                    </span>
                  </td>
                  <td>
                    {a.is_delivered ? 
                      <span className="badge success">Delivered</span> : 
                      <span className="badge warning">Pending</span>
                    }
                  </td>
                </tr>
              ))}
              {articles.length === 0 && !loading && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
                    <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', color: 'var(--text-muted)' }}>
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline>
                      </svg>
                      <div>
                        <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>No intelligence yet</p>
                        <p style={{ fontSize: '0.875rem' }}>Add some RSS sources in settings to get started.</p>
                      </div>
                    </div>
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
