import { useState, useEffect, useRef } from 'react';
import { supabase } from '../supabase';
import { Trash2, Plus, Pencil, Check, X, Upload, ChevronDown, ChevronUp, Rss, Brain, Webhook } from 'lucide-react';

/* ─── tiny helpers ─────────────────────────────────────────────────────── */
const Section = ({ icon: Icon, title, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="settings-section glass-panel">
      <button
        className="section-header secondary"
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', justifyContent: 'space-between', padding: '1.25rem 1.5rem', borderRadius: open ? '12px 12px 0 0' : '12px', border: 'none', borderBottom: open ? '1px solid var(--card-border)' : 'none' }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
          <Icon size={18} style={{ color: 'var(--accent)' }} />
          {title}
        </span>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>
      {open && <div style={{ padding: '1.5rem' }}>{children}</div>}
    </div>
  );
};

/* ─── main component ────────────────────────────────────────────────────── */
export default function SettingsView({ session }) {
  /* ── RSS sources ── */
  const [sources, setSources]           = useState([]);
  const [newName, setNewName]           = useState('');
  const [newUrl, setNewUrl]             = useState('');
  const [editId, setEditId]             = useState(null);
  const [editName, setEditName]         = useState('');
  const [editUrl, setEditUrl]           = useState('');
  const [sourceMsg, setSourceMsg]       = useState(null);
  const fileInputRef                    = useRef(null);

  /* ── topics ── */
  const [topics, setTopics]             = useState({ allowed: [], blocked: [], priority: [] });
  const [allowedInput, setAllowedInput] = useState('');
  const [blockedInput, setBlockedInput] = useState('');
  const [priorityInput, setPriorityInput] = useState('');
  const [topicMsg, setTopicMsg]         = useState(null);

  /* ── webhooks ── */
  const [webhooks, setWebhooks]         = useState({ slack: '', discord: '' });
  const [webhookMsg, setWebhookMsg]     = useState(null);

  useEffect(() => { fetchSources(); fetchTopics(); fetchWebhooks(); }, [session]);

  /* ─── flash helper ─── */
  const flash = (setter, msg, isErr = false) => {
    setter({ text: msg, err: isErr });
    setTimeout(() => setter(null), 3000);
  };

  /* ─── RSS CRUD ─── */
  const fetchSources = async () => {
    const { data } = await supabase.from('rss_sources').select('*').order('name');
    if (data) setSources(data);
  };

  const addSource = async (e) => {
    e.preventDefault();
    if (!newName.trim() || !newUrl.trim()) return;
    const { error } = await supabase.from('rss_sources').insert({ name: newName.trim(), url: newUrl.trim(), user_id: session.user.id });
    if (error) { flash(setSourceMsg, 'Error: ' + error.message, true); return; }
    setNewName(''); setNewUrl('');
    fetchSources();
    flash(setSourceMsg, 'Source added ✓');
  };

  const deleteSource = async (id) => {
    await supabase.from('rss_sources').delete().eq('id', id);
    fetchSources();
  };

  const startEdit = (s) => { setEditId(s.id); setEditName(s.name); setEditUrl(s.url); };
  const cancelEdit = () => { setEditId(null); setEditName(''); setEditUrl(''); };

  const saveEdit = async (id) => {
    const { error } = await supabase.from('rss_sources').update({ name: editName.trim(), url: editUrl.trim() }).eq('id', id);
    if (error) { flash(setSourceMsg, 'Error: ' + error.message, true); return; }
    cancelEdit();
    fetchSources();
    flash(setSourceMsg, 'Source updated ✓');
  };

  /* ─── File upload (bulk import) ─── */
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    e.target.value = ''; // reset input so same file can be re-selected

    let text;
    try {
      text = await file.text();
    } catch {
      flash(setSourceMsg, 'Could not read file.', true);
      return;
    }

    // Handle both \r\n (Windows) and \n (Unix) line endings
    const lines = text
      .split(/\r?\n/)
      .map(l => l.trim())
      .filter(l => l && !l.startsWith('#')); // skip empty lines and comments

    const existingUrls = new Set(sources.map(s => s.url.toLowerCase()));
    const rows = [];
    const skipped = [];
    const invalid = [];

    for (const line of lines) {
      let name = '', url = '';

      if (line.includes('|')) {
        [name, url] = line.split('|').map(s => s.trim());
      } else if (line.startsWith('http')) {
        url = line.trim();
        try { name = new URL(url).hostname.replace(/^www\./, ''); } catch { name = url; }
      } else {
        invalid.push(line);
        continue;
      }

      // Validate URL
      try { new URL(url); } catch {
        invalid.push(line);
        continue;
      }

      if (!name || !url) { invalid.push(line); continue; }

      // Deduplicate against existing sources
      if (existingUrls.has(url.toLowerCase())) {
        skipped.push(name);
        continue;
      }

      existingUrls.add(url.toLowerCase()); // prevent dupes within the file itself
      rows.push({ name, url, user_id: session.user.id });
    }

    if (rows.length === 0) {
      const reason = skipped.length > 0
        ? `All ${skipped.length} feed(s) already exist.`
        : invalid.length > 0
          ? `No valid entries found. Check file format.`
          : 'File appears empty.';
      flash(setSourceMsg, reason, true);
      return;
    }

    // Insert in batches of 10 to avoid request size limits
    let inserted = 0;
    let errors = [];
    for (let i = 0; i < rows.length; i += 10) {
      const batch = rows.slice(i, i + 10);
      const { error } = await supabase.from('rss_sources').insert(batch);
      if (error) errors.push(error.message);
      else inserted += batch.length;
    }

    await fetchSources();

    if (errors.length > 0) {
      flash(setSourceMsg, `Imported ${inserted}, failed ${errors.length}: ${errors[0]}`, true);
    } else {
      const parts = [`Imported ${inserted} source(s) ✓`];
      if (skipped.length) parts.push(`${skipped.length} already existed`);
      if (invalid.length) parts.push(`${invalid.length} invalid line(s) skipped`);
      flash(setSourceMsg, parts.join(' · '));
    }
  };

  /* ─── Topics ─── */
  const fetchTopics = async () => {
    const { data } = await supabase.from('app_config').select('value').eq('key', 'topics').single();
    if (data?.value) {
      setTopics(data.value);
      setAllowedInput(data.value.allowed?.join(', ') || '');
      setBlockedInput(data.value.blocked?.join(', ') || '');
      setPriorityInput(data.value.priority?.join(', ') || '');
    }
  };

  const saveTopics = async () => {
    const clean = str => str.split(',').map(s => s.trim()).filter(Boolean);
    const val = { allowed: clean(allowedInput), blocked: clean(blockedInput), priority: clean(priorityInput) };
    const { data } = await supabase.from('app_config').select('key').eq('key', 'topics').single();
    if (data) await supabase.from('app_config').update({ value: val }).eq('key', 'topics');
    else       await supabase.from('app_config').insert({ key: 'topics', value: val, user_id: session.user.id });
    flash(setTopicMsg, 'Processing rules saved ✓');
  };

  /* ─── Webhooks ─── */
  const fetchWebhooks = async () => {
    const { data } = await supabase.from('tenant_profiles').select('*').single();
    if (data) setWebhooks({ slack: data.slack_webhook_url || '', discord: data.discord_webhook_url || '' });
  };

  const saveWebhooks = async () => {
    const { error } = await supabase.from('tenant_profiles').upsert({ user_id: session.user.id, slack_webhook_url: webhooks.slack, discord_webhook_url: webhooks.discord });
    if (error) flash(setWebhookMsg, 'Error: ' + error.message, true);
    else        flash(setWebhookMsg, 'Endpoints saved ✓');
  };

  /* ─── render ─── */
  return (
    <div>
      {/* Page header */}
      <div className="header">
        <h1>Configuration</h1>
      </div>

      <div className="settings-grid">

        {/* ── SECTION 1: RSS Sources ─────────────────────────────────────── */}
        <Section icon={Rss} title="RSS Sources">

          {/* Flash message */}
          {sourceMsg && (
            <div style={{ padding: '0.6rem 1rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem',
              background: sourceMsg.err ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
              color: sourceMsg.err ? '#fca5a5' : '#6ee7b7', border: `1px solid ${sourceMsg.err ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}` }}>
              {sourceMsg.text}
            </div>
          )}

          {/* Sources list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
            {sources.length === 0 && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', textAlign: 'center', padding: '1.5rem' }}>
                No sources yet. Add one below or import a file.
              </p>
            )}
            {sources.map(s => (
              <div key={s.id} className="source-row">
                {editId === s.id ? (
                  /* ── Edit mode ── */
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.6rem', paddingRight: '1rem' }}>
                    <div>
                      <label className="field-label" style={{ fontSize: '0.7rem' }}>Feed Name</label>
                      <input value={editName} onChange={e => setEditName(e.target.value)} placeholder="e.g. OpenAI Blog" style={{ marginBottom: 0 }} />
                    </div>
                    <div>
                      <label className="field-label" style={{ fontSize: '0.7rem' }}>RSS URL</label>
                      <input value={editUrl}  onChange={e => setEditUrl(e.target.value)}  placeholder="https://..."  style={{ marginBottom: 0 }} />
                    </div>
                  </div>
                ) : (
                  /* ── View mode ── */
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, marginBottom: '0.15rem' }}>{s.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.url}</div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}>
                  {editId === s.id ? (
                    <>
                      <button onClick={() => saveEdit(s.id)} style={{ padding: '0.5rem', background: 'rgba(16,185,129,0.2)', border: '1px solid rgba(16,185,129,0.4)' }} title="Save">
                        <Check size={15} color="#6ee7b7" />
                      </button>
                      <button onClick={cancelEdit} className="secondary" style={{ padding: '0.5rem' }} title="Cancel">
                        <X size={15} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => startEdit(s)} className="secondary" style={{ padding: '0.5rem' }} title="Edit">
                        <Pencil size={15} color="#94a3b8" />
                      </button>
                      <button onClick={() => deleteSource(s.id)} className="secondary" style={{ padding: '0.5rem' }} title="Delete">
                        <Trash2 size={15} color="#ef4444" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Add single source */}
          <form onSubmit={addSource} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: '1 1 200px' }}>
                <label className="field-label">Feed Name</label>
                <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. Hugging Face" style={{ marginBottom: 0 }} />
              </div>
              <div style={{ flex: '2 1 280px' }}>
                <label className="field-label">RSS URL</label>
                <input value={newUrl}  onChange={e => setNewUrl(e.target.value)}  placeholder="https://..." style={{ marginBottom: 0 }} />
              </div>
              <button type="submit" style={{ flexShrink: 0, padding: '0.75rem 1.5rem', marginBottom: '0' }}>
                <Plus size={18} /> Add Source
              </button>
            </div>
          </form>

          {/* Bulk import via file */}
          <div style={{ borderTop: '1px solid var(--card-border)', paddingTop: '1rem' }}>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              📄 <strong style={{ color: 'var(--text-primary)' }}>Bulk import via file</strong> — upload a <code>.txt</code> file to import hundreds of feeds at once. Format one entry per line:
              <code style={{ display: 'block', marginTop: '0.5rem', padding: '0.75rem 1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '0.75rem', border: '1px solid var(--card-border)' }}>
                Feed Name | https://example.com/feed<br />https://plainurl.com/rss
              </code>
            </p>
            <input ref={fileInputRef} type="file" accept=".txt,.csv" onChange={handleFileUpload} style={{ display: 'none' }} />
            <button type="button" className="secondary" onClick={() => fileInputRef.current?.click()} style={{ width: 'auto' }}>
              <Upload size={16} /> Upload .txt File
            </button>
          </div>
        </Section>

        {/* ── SECTION 2: Intelligence Engine ───────────────────────────── */}
        <Section icon={Brain} title="Intelligence Engine">

          {topicMsg && (
            <div style={{ padding: '0.6rem 1rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem',
              background: topicMsg.err ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
              color: topicMsg.err ? '#fca5a5' : '#6ee7b7', border: `1px solid ${topicMsg.err ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}` }}>
              {topicMsg.text}
            </div>
          )}

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
            Define what you care about. Separate keywords with commas.
          </p>

          <div className="topic-grid">
            <div>
              <label className="field-label">✅ Allowed Topics</label>
              <textarea rows={3} value={allowedInput} onChange={e => setAllowedInput(e.target.value)} placeholder="ai, llm, machine learning, python..." />
            </div>
            <div>
              <label className="field-label">🚫 Blocked Topics</label>
              <textarea rows={3} value={blockedInput} onChange={e => setBlockedInput(e.target.value)} placeholder="hiring, crypto, nft..." />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label className="field-label">🚀 Priority Keywords <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>(+1.5 score boost)</span></label>
              <textarea rows={2} value={priorityInput} onChange={e => setPriorityInput(e.target.value)} placeholder="launch, open source, breakthrough..." />
            </div>
          </div>

          <button onClick={saveTopics} style={{ marginTop: '1rem' }}>
            Save Processing Rules
          </button>
        </Section>

        {/* ── SECTION 3: Delivery Channels ─────────────────────────────── */}
        <Section icon={Webhook} title="Delivery Channels" defaultOpen={false}>

          {webhookMsg && (
            <div style={{ padding: '0.6rem 1rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem',
              background: webhookMsg.err ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
              color: webhookMsg.err ? '#fca5a5' : '#6ee7b7', border: `1px solid ${webhookMsg.err ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}` }}>
              {webhookMsg.text}
            </div>
          )}

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
            Connect your endpoints to receive intelligent digests automatically.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <label className="field-label">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <svg width="16" height="16" viewBox="0 0 127 127" fill="#4A154B"><path d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9zm6.5 0c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V77.6z"/><path d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9H45.2zm0 6.5c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9h32.3z"/><path d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9 7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H97V45.2zm-6.5 0c0 7.1-5.8 12.9-12.9 12.9-7.1 0-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0c7.1 0 12.9 5.8 12.9 12.9v32.3z"/><path d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9 0 7.1-5.8 12.9-12.9 12.9-7.1 0-12.9-5.8-12.9-12.9V97h12.9zm0-6.5c-7.1 0-12.9-5.8-12.9-12.9 0-7.1 5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9 0 7.1-5.8 12.9-12.9 12.9H77.6z"/></svg>
                Slack Webhook
              </span>
            </label>
            <input value={webhooks.slack} onChange={e => setWebhooks({ ...webhooks, slack: e.target.value })} placeholder="https://hooks.slack.com/services/..." />

            <label className="field-label">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <svg width="16" height="16" viewBox="0 0 71 55" fill="#5865F2"><path d="M60.1 4.9A58.6 58.6 0 0 0 45.5 0a40.9 40.9 0 0 0-1.8 3.7 54.2 54.2 0 0 0-16.4 0A40.9 40.9 0 0 0 25.5 0 58.5 58.5 0 0 0 10.9 4.9C1.6 18.7-1 32.2.3 45.5a59.1 59.1 0 0 0 18 9.1 44.3 44.3 0 0 0 3.8-6.2 38.4 38.4 0 0 1-6-2.9l1.5-1.1a42.1 42.1 0 0 0 36.1 0l1.5 1.1a38.4 38.4 0 0 1-6 2.9 44.3 44.3 0 0 0 3.8 6.2 58.9 58.9 0 0 0 18-9.1C72 30.2 68.3 16.8 60.1 4.9ZM23.7 37.3c-3.5 0-6.4-3.2-6.4-7.2s2.8-7.2 6.4-7.2 6.4 3.2 6.4 7.2-2.8 7.2-6.4 7.2Zm23.7 0c-3.5 0-6.4-3.2-6.4-7.2s2.8-7.2 6.4-7.2 6.4 3.2 6.4 7.2-2.8 7.2-6.4 7.2Z"/></svg>
                Discord Webhook
              </span>
            </label>
            <input value={webhooks.discord} onChange={e => setWebhooks({ ...webhooks, discord: e.target.value })} placeholder="https://discord.com/api/webhooks/..." />
          </div>

          <button onClick={saveWebhooks} style={{ marginTop: '1.5rem' }}>
            Save Webhook Endpoints
          </button>
        </Section>

      </div>
    </div>
  );
}
