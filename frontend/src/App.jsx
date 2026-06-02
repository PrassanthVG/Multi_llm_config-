import { useState, useEffect, useCallback } from "react";

const API = `${window.location.protocol}//${window.location.hostname}:8000/api`;

const PROVIDER_PRESETS = [
  { label: "Vast AI", api_base_hint: "http://<IP>:<PORT>/v1", notes: "Vast AI rented GPU VM" },
  { label: "Scaleway", api_base_hint: "https://api.scaleway.ai/v1", notes: "Scaleway Generative APIs" },
  { label: "vLLM (self-hosted)", api_base_hint: "http://<VM_IP>:8000/v1", notes: "Self-hosted vLLM server" },
  { label: "Ollama (local)", api_base_hint: "http://localhost:11434/v1", notes: "Local Ollama instance" },
  { label: "OpenAI", api_base_hint: "https://api.openai.com/v1", notes: "OpenAI API" },
  { label: "Custom OpenAI-compatible", api_base_hint: "", notes: "" },
];

const STATUS_COLOR = {
  healthy: "#22c55e",
  unreachable: "#ef4444",
  unknown: "#f59e0b",
};

function Badge({ children, color = "#334155", bg = "#1e293b" }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, letterSpacing: "0.06em",
      padding: "2px 8px", borderRadius: 4,
      background: bg, color,
      border: `1px solid ${color}22`,
      fontFamily: "'JetBrains Mono', monospace",
      textTransform: "uppercase",
    }}>{children}</span>
  );
}

function Tag({ type }) {
  const colors = {
    llm: { bg: "#0f2d4a", color: "#38bdf8" },
    vlm: { bg: "#1a1a3e", color: "#a78bfa" },
  };
  const c = colors[type] || colors.llm;
  return <Badge color={c.color} bg={c.bg}>{type}</Badge>;
}

function StatusDot({ active }) {
  return (
    <span style={{
      display: "inline-block", width: 8, height: 8, borderRadius: "50%",
      background: active ? "#22c55e" : "#475569",
      boxShadow: active ? "0 0 6px #22c55e88" : "none",
      marginRight: 6,
    }} />
  );
}

function Modal({ open, onClose, children, title }) {
  if (!open) return null;
  return (
    <div style={{
      position: "fixed", inset: 0, background: "#00000099", zIndex: 100,
      display: "flex", alignItems: "center", justifyContent: "center",
      backdropFilter: "blur(4px)",
    }} onClick={onClose}>
      <div style={{
        background: "#0f172a", border: "1px solid #1e293b",
        borderRadius: 12, padding: 32, width: "min(560px, 95vw)",
        maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 24px 64px #000a",
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h2 style={{ margin: 0, fontSize: 18, color: "#f1f5f9", fontWeight: 600 }}>{title}</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 20 }}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Input({ label, value, onChange, type = "text", placeholder, mono, required }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 500, letterSpacing: "0.04em" }}>
        {label}{required && <span style={{ color: "#f87171", marginLeft: 2 }}>*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        style={{
          width: "100%", padding: "10px 12px", borderRadius: 8,
          background: "#0b1628", border: "1px solid #1e293b",
          color: "#e2e8f0", fontSize: 13,
          fontFamily: mono ? "'JetBrains Mono', monospace" : "inherit",
          outline: "none", boxSizing: "border-box",
          transition: "border-color 0.15s",
        }}
        onFocus={e => e.target.style.borderColor = "#38bdf8"}
        onBlur={e => e.target.style.borderColor = "#1e293b"}
      />
    </div>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 500, letterSpacing: "0.04em" }}>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} style={{
        width: "100%", padding: "10px 12px", borderRadius: 8,
        background: "#0b1628", border: "1px solid #1e293b",
        color: "#e2e8f0", fontSize: 13, outline: "none", cursor: "pointer", boxSizing: "border-box",
      }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function Button({ onClick, children, variant = "primary", disabled, small }) {
  const variants = {
    primary: { background: "#0ea5e9", color: "#fff" },
    danger:  { background: "#dc2626", color: "#fff" },
    ghost:   { background: "transparent", color: "#94a3b8", border: "1px solid #1e293b" },
    success: { background: "#16a34a", color: "#fff" },
    warning: { background: "#d97706", color: "#fff" },
  };
  const s = variants[variant];
  return (
    <button onClick={onClick} disabled={disabled} style={{
      ...s, border: s.border || "none",
      borderRadius: 7, padding: small ? "5px 12px" : "9px 18px",
      fontSize: small ? 12 : 13, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1, transition: "opacity 0.15s, transform 0.1s",
      letterSpacing: "0.02em",
    }}
    onMouseDown={e => !disabled && (e.currentTarget.style.transform = "scale(0.97)")}
    onMouseUp={e => e.currentTarget.style.transform = "scale(1)"}
    >{children}</button>
  );
}

function TestPanel({ providers }) {
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("Hello! What model are you and who made you?");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(null);

  const activeProviders = providers.filter(p => p.is_active);

  const run = async () => {
    setLoading(true); setResult(null); setError(null); setElapsed(null);
    const t = Date.now();
    try {
      const endpoint = model ? `/api/proxy/chat/model/${model}` : "/api/proxy/chat";
      const r = await fetch(API.replace("/api", "") + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: prompt }] }),
      });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      setResult(data.choices?.[0]?.message?.content || JSON.stringify(data, null, 2));
      setElapsed(Date.now() - t);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "#0b1120", border: "1px solid #1e293b", borderRadius: 12, padding: 24 }}>
      <h3 style={{ margin: "0 0 20px", color: "#f1f5f9", fontSize: 15, fontWeight: 600 }}>🧪 Test a Provider</h3>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 500 }}>Provider alias</label>
        <select value={model} onChange={e => setModel(e.target.value)} style={{
          width: "100%", padding: "10px 12px", borderRadius: 8, background: "#0b1628",
          border: "1px solid #1e293b", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box",
        }}>
          <option value="">— use default LLM —</option>
          {activeProviders.map(p => <option key={p.name} value={p.name}>{p.display_name} ({p.name})</option>)}
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 500 }}>Prompt</label>
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={3} style={{
          width: "100%", padding: "10px 12px", borderRadius: 8, background: "#0b1628",
          border: "1px solid #1e293b", color: "#e2e8f0", fontSize: 13, resize: "vertical",
          outline: "none", boxSizing: "border-box", fontFamily: "inherit",
        }} />
      </div>
      <Button onClick={run} disabled={loading}>{loading ? "Running…" : "▶ Run"}</Button>
      {elapsed && <span style={{ fontSize: 12, color: "#64748b", marginLeft: 12 }}>{elapsed}ms</span>}
      {error && <div style={{ marginTop: 16, padding: 12, background: "#300", borderRadius: 8, color: "#fca5a5", fontSize: 13, fontFamily: "monospace" }}>{error}</div>}
      {result && (
        <div style={{ marginTop: 16, padding: 16, background: "#0f2130", borderRadius: 8, border: "1px solid #1e3a5f" }}>
          <div style={{ fontSize: 11, color: "#38bdf8", marginBottom: 8, fontWeight: 600, letterSpacing: "0.06em" }}>RESPONSE</div>
          <pre style={{ margin: 0, color: "#e2e8f0", fontSize: 13, whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{result}</pre>
        </div>
      )}
    </div>
  );
}

function ProviderForm({ initial, onSubmit, onClose, loading }) {
  const [form, setForm] = useState({
    name: "", display_name: "", provider_type: "llm",
    model_name: "", api_base: "", api_key: "", notes: "", is_active: true,
    ...initial,
  });
  const [preset, setPreset] = useState("");

  const set = k => v => setForm(f => ({ ...f, [k]: v }));

  const applyPreset = (label) => {
    const p = PROVIDER_PRESETS.find(x => x.label === label);
    if (p) setForm(f => ({ ...f, api_base: p.api_base_hint, notes: p.notes }));
    setPreset(label);
  };

  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit(form); }} style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 500 }}>Quick preset</label>
        <select value={preset} onChange={e => applyPreset(e.target.value)} style={{
          width: "100%", padding: "10px 12px", borderRadius: 8, background: "#0b1628",
          border: "1px solid #1e293b", color: "#e2e8f0", fontSize: 13, outline: "none", boxSizing: "border-box",
        }}>
          <option value="">— choose preset (optional) —</option>
          {PROVIDER_PRESETS.map(p => <option key={p.label} value={p.label}>{p.label}</option>)}
        </select>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        <Input label="Alias (used in code)" value={form.name} onChange={set("name")} placeholder="vast-llm" mono required />
        <Input label="Display name" value={form.display_name} onChange={set("display_name")} placeholder="Vast AI LLM" required />
      </div>
      <Select
        label="Type" value={form.provider_type} onChange={set("provider_type")}
        options={[{ value: "llm", label: "LLM (text)" }, { value: "vlm", label: "VLM (vision)" }]}
      />
      <Input label="Model name (sent to provider)" value={form.model_name} onChange={set("model_name")} placeholder="sorc/qwen3.5-instruct:latest" mono required />
      <Input label="API Base URL" value={form.api_base} onChange={set("api_base")} placeholder="http://109.165.142.5:30203/v1" mono required />
      <Input label="API Key / Bearer Token" value={form.api_key} onChange={set("api_key")} type="password" placeholder="fe83463d..." mono required />
      <Input label="Notes (optional)" value={form.notes || ""} onChange={set("notes")} placeholder="Vast AI VM, rented until..." />
      <div style={{ display: "flex", gap: 12, marginTop: 8, justifyContent: "flex-end" }}>
        <Button onClick={onClose} variant="ghost" type="button">Cancel</Button>
        <Button type="submit" disabled={loading}>{loading ? "Saving…" : "Save provider"}</Button>
      </div>
    </form>
  );
}

function ProviderCard({ provider, onRefresh, onEdit }) {
  const [busy, setBusy] = useState(false);

  const action = async (url, method = "POST") => {
    setBusy(true);
    try {
      await fetch(`${API}/providers${url}`, { method });
      await onRefresh();
    } finally { setBusy(false); }
  };

  return (
    <div style={{
      background: "#0b1120", border: `1px solid ${provider.is_active ? "#1e293b" : "#0f172a"}`,
      borderRadius: 12, padding: 20, opacity: provider.is_active ? 1 : 0.6,
      transition: "border-color 0.2s, opacity 0.2s",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <StatusDot active={provider.is_active} />
            <span style={{ fontWeight: 600, color: "#f1f5f9", fontSize: 15 }}>{provider.display_name}</span>
            <Tag type={provider.provider_type} />
            {provider.is_default_llm && <Badge color="#fbbf24" bg="#1c1500">default llm</Badge>}
            {provider.is_default_vlm && <Badge color="#a78bfa" bg="#1a1030">default vlm</Badge>}
          </div>
          <code style={{ fontSize: 11, color: "#64748b", fontFamily: "'JetBrains Mono', monospace" }}>{provider.name}</code>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <Button onClick={() => onEdit(provider)} variant="ghost" small>Edit</Button>
          <Button onClick={() => action(`/${provider.id}/set-default`)} variant="warning" small disabled={busy}>★</Button>
          {provider.is_active
            ? <Button onClick={() => action(`/${provider.id}/deactivate`)} variant="ghost" small disabled={busy}>Pause</Button>
            : <Button onClick={() => action(`/${provider.id}/activate`)} variant="success" small disabled={busy}>Activate</Button>
          }
          <Button onClick={() => action(`/${provider.id}`, "DELETE") } variant="danger" small disabled={busy}>✕</Button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        {[
          ["Model", provider.model_name],
          ["Base URL", provider.api_base],
          ["Token", "••••••••" + provider.api_key.slice(-6)],
          ["Added", new Date(provider.created_at).toLocaleDateString()],
        ].map(([k, v]) => (
          <div key={k} style={{ background: "#0f172a", borderRadius: 6, padding: "8px 12px" }}>
            <div style={{ fontSize: 10, color: "#475569", fontWeight: 600, letterSpacing: "0.06em", marginBottom: 3 }}>{k}</div>
            <div style={{ fontSize: 12, color: "#94a3b8", fontFamily: k === "Model" || k === "Base URL" || k === "Token" ? "'JetBrains Mono', monospace" : "inherit", wordBreak: "break-all" }}>{v}</div>
          </div>
        ))}
      </div>

      {provider.notes && (
        <div style={{ marginTop: 10, fontSize: 12, color: "#64748b", fontStyle: "italic" }}>{provider.notes}</div>
      )}
    </div>
  );
}

export default function App() {
  const [providers, setProviders] = useState([]);
  const [health, setHealth] = useState(null);
  const [defaults, setDefaults] = useState({ default_llm: null, default_vlm: null });
  const [showAdd, setShowAdd] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState("providers");
  const [filter, setFilter] = useState("all");

  const loadProviders = useCallback(async () => {
    try {
      const [pRes, dRes, hRes] = await Promise.all([
        fetch(`${API}/providers/`),
        fetch(`${API}/providers/defaults/active`),
        fetch(`${API}/health/`),
      ]);
      setProviders(await pRes.json());
      setDefaults(await dRes.json());
      setHealth(await hRes.json());
    } catch {}
  }, []);

  useEffect(() => { loadProviders(); const t = setInterval(loadProviders, 10000); return () => clearInterval(t); }, [loadProviders]);

  const handleAdd = async (form) => {
    setSaving(true);
    try {
      const r = await fetch(`${API}/providers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!r.ok) throw new Error(await r.text());
      await loadProviders();
      setShowAdd(false);
    } catch (e) { alert("Error: " + e.message); }
    finally { setSaving(false); }
  };

  const handleEdit = async (form) => {
    setSaving(true);
    try {
      const r = await fetch(`${API}/providers/${editTarget.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!r.ok) throw new Error(await r.text());
      await loadProviders();
      setEditTarget(null);
    } catch (e) { alert("Error: " + e.message); }
    finally { setSaving(false); }
  };

  const filtered = providers.filter(p => {
    if (filter === "llm") return p.provider_type === "llm";
    if (filter === "vlm") return p.provider_type === "vlm";
    if (filter === "active") return p.is_active;
    return true;
  });

  const proxyStatus = health?.litellm_proxy || "unknown";

  return (
    <div style={{ minHeight: "100vh", background: "#060d1a", color: "#e2e8f0", fontFamily: "'DM Sans', 'Segoe UI', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

      {/* Header */}
      <header style={{ borderBottom: "1px solid #1e293b", padding: "16px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#080e1a" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg,#0ea5e9,#6366f1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>⚡</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: "#f1f5f9", letterSpacing: "-0.02em" }}>MuruganAI</div>
            <div style={{ fontSize: 11, color: "#475569" }}>Provider Gateway</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#64748b" }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: STATUS_COLOR[proxyStatus] || "#f59e0b", display: "inline-block", boxShadow: `0 0 6px ${STATUS_COLOR[proxyStatus] || "#f59e0b"}88` }} />
            LiteLLM {proxyStatus}
          </div>
          {defaults.default_llm && <Badge color="#38bdf8" bg="#0f2d4a">LLM: {defaults.default_llm}</Badge>}
          {defaults.default_vlm && <Badge color="#a78bfa" bg="#1a1030">VLM: {defaults.default_vlm}</Badge>}
          <Button onClick={() => setShowAdd(true)}>+ Add provider</Button>
        </div>
      </header>

      {/* Tabs */}
      <div style={{ borderBottom: "1px solid #1e293b", padding: "0 32px", display: "flex", gap: 0 }}>
        {["providers", "test", "config"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: "none", border: "none", cursor: "pointer",
            padding: "14px 20px", fontSize: 13, fontWeight: tab === t ? 600 : 400,
            color: tab === t ? "#38bdf8" : "#64748b",
            borderBottom: tab === t ? "2px solid #38bdf8" : "2px solid transparent",
            textTransform: "capitalize", transition: "color 0.15s",
          }}>{t}</button>
        ))}
      </div>

      <div style={{ padding: "32px", maxWidth: 1100, margin: "0 auto" }}>

        {tab === "providers" && (
          <>
            {/* Filter row */}
            <div style={{ display: "flex", gap: 8, marginBottom: 24, alignItems: "center" }}>
              <span style={{ fontSize: 13, color: "#64748b", marginRight: 4 }}>Filter:</span>
              {["all", "llm", "vlm", "active"].map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{
                  padding: "5px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500,
                  border: `1px solid ${filter === f ? "#38bdf8" : "#1e293b"}`,
                  background: filter === f ? "#0f2d4a" : "transparent",
                  color: filter === f ? "#38bdf8" : "#64748b",
                  cursor: "pointer", textTransform: "capitalize",
                }}>{f}</button>
              ))}
              <span style={{ marginLeft: "auto", fontSize: 12, color: "#475569" }}>{filtered.length} provider{filtered.length !== 1 ? "s" : ""}</span>
            </div>

            {filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: "64px 0" }}>
                <div style={{ fontSize: 40, marginBottom: 16 }}>🔌</div>
                <div style={{ color: "#475569", marginBottom: 20 }}>No providers configured yet.</div>
                <Button onClick={() => setShowAdd(true)}>Add your first provider</Button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {filtered.map(p => (
                  <ProviderCard key={p.id} provider={p} onRefresh={loadProviders} onEdit={setEditTarget} />
                ))}
              </div>
            )}
          </>
        )}

        {tab === "test" && <TestPanel providers={providers} />}

        {tab === "config" && (
          <div>
            <h3 style={{ color: "#f1f5f9", marginTop: 0 }}>How to use in main.py</h3>
            <pre style={{
              background: "#0b1120", border: "1px solid #1e293b", borderRadius: 12,
              padding: 24, color: "#e2e8f0", fontSize: 13, lineHeight: 1.7,
              fontFamily: "'JetBrains Mono', monospace", overflow: "auto",
            }}>{`# main.py — replace all DYNAMIC_* env vars with just these

import httpx, os

GATEWAY_URL = "${window.location.protocol}//${window.location.hostname}:8000"
GATEWAY_KEY = "sk-murugan-gateway-2024"

_client = httpx.AsyncClient(
    base_url=GATEWAY_URL,
    headers={"Authorization": f"Bearer {GATEWAY_KEY}"},
    timeout=120,
)

# ✅ Use default LLM (set in UI with ★)
async def call_llm(messages):
    r = await _client.post("/api/proxy/chat",
        json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]

# ✅ Use default VLM
async def call_vlm(messages):
    r = await _client.post("/api/proxy/chat/vlm",
        json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]

# ✅ Use a specific provider by alias
async def call_provider(alias, messages):
    r = await _client.post(f"/api/proxy/chat/model/{alias}",
        json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]

# Active providers registered:
${providers.filter(p => p.is_active).map(p => `#   "${p.name}" → ${p.model_name}`).join("\n") || "#   (none yet — add providers above)"}
`}</pre>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 24 }}>
              {[
                ["Gateway URL", `${window.location.protocol}//${window.location.hostname}:8000`],
                ["LiteLLM Proxy", `${window.location.protocol}//${window.location.hostname}:4000`],
                ["Chat endpoint", "/api/proxy/chat"],
                ["VLM endpoint", "/api/proxy/chat/vlm"],
              ].map(([k, v]) => (
                <div key={k} style={{ background: "#0b1120", border: "1px solid #1e293b", borderRadius: 8, padding: "12px 16px", minWidth: 200 }}>
                  <div style={{ fontSize: 10, color: "#475569", fontWeight: 600, letterSpacing: "0.06em", marginBottom: 4 }}>{k}</div>
                  <code style={{ fontSize: 12, color: "#38bdf8", fontFamily: "'JetBrains Mono', monospace" }}>{v}</code>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Add Modal */}
      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Add provider">
        <ProviderForm onSubmit={handleAdd} onClose={() => setShowAdd(false)} loading={saving} />
      </Modal>

      {/* Edit Modal */}
      <Modal open={!!editTarget} onClose={() => setEditTarget(null)} title="Edit provider">
        {editTarget && <ProviderForm initial={editTarget} onSubmit={handleEdit} onClose={() => setEditTarget(null)} loading={saving} />}
      </Modal>
    </div>
  );
}
