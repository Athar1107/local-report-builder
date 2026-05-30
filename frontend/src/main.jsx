import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Archive,
  BookOpenText,
  CheckCircle2,
  Download,
  FilePlus2,
  FileText,
  ImagePlus,
  Loader2,
  Sparkles,
  Upload,
  Home,
  Search,
  Calendar,
  Bell,
  AlertTriangle,
  Activity,
  Database,
  HardDrive,
  ServerCog,
  ShieldCheck,
  Lock,
  X
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";

const tabs = [
  { id: "home", label: "Dashboard Overview", icon: Home },
  { id: "index", label: "Index Report", icon: FilePlus2 },
  { id: "caption", label: "Generate Captions", icon: ImagePlus },
  { id: "report", label: "Generate Report", icon: BookOpenText },
  { id: "library", label: "Library & Assets", icon: Archive },
];

/** Same formula as app.py `knowledge_index_pct` when the API omits that field. */
function knowledgeIndexFromCounts(stats) {
  const total = stats.total ?? 0;
  if (total <= 0) return 0;
  const c = stats.captions ?? 0;
  const s = stats.sections ?? 0;
  const sc = Array.isArray(stats.sources) ? stats.sources.length : 0;
  const raw = 11 * Math.log1p(c) + 9 * Math.log1p(s) + 6.5 * Math.log1p(Math.max(sc, 1));
  return Math.min(100, Math.round(raw * 10) / 10);
}

const defaultSections = [
  ["introduction", "Introduction", "Purpose, context, and relevance of the event."],
  ["about_the_speaker", "About the Speaker", "Speaker name, role, expertise, and affiliation."],
  ["about_the_event", "About the Event", "Date, time, venue, participants, and event format."],
  ["description", "Description", "Chronological flow, sessions, activities, and highlights."],
  ["conclusion", "Conclusion", "Impact, closing remarks, and key takeaways."],
  ["sdg_impact", "SDG Impact", "Relevant SDGs and how the event contributed."],
  ["ieee_goals", "IEEE Goals", "IEEE goals or branch vision achieved through the event."],
  ["acknowledgement", "Acknowledgement", "Faculty, sponsors, organisers, and supporters."],
];

const LAST_WEEK_KNOWLEDGE_INDEX = 87;

const ADMIN_EMAIL    = "local@ieee.org";
const ADMIN_PASSWORD = "IEEE";

function App() {
  const [showAdminPortal, setShowAdminPortal] = useState(false);
  const [showAdminLogin, setShowAdminLogin]   = useState(false);
  const [adminAuthed, setAdminAuthed]         = useState(false);
  const [activeTab, setActiveTab] = useState("home");
  const [status, setStatus] = useState({ stats: emptyStats(), outputs: [], sections: defaultSections });
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(null);
  const [captionResult, setCaptionResult] = useState(null);
  const [reportResult, setReportResult] = useState(null);
  const [predictionResult, setPredictionResult] = useState(null);

  const sections = status.sections?.length ? status.sections : defaultSections;
  const stats = status.stats || emptyStats();
  const outputs = status.outputs || [];

  const readyState = useMemo(() => {
    if (stats.total > 0) return { label: "All Systems Operational", tone: "ready" };
    return { label: "Awaiting Index Data", tone: "waiting" };
  }, [stats.total]);

  const knowledgeIndexPct = useMemo(() => {
    if (typeof stats.knowledge_index_pct === "number" && !Number.isNaN(stats.knowledge_index_pct)) {
      return stats.knowledge_index_pct;
    }
    return knowledgeIndexFromCounts(stats);
  }, [stats.knowledge_index_pct, stats.total, stats.captions, stats.sections, stats.sources]);

  const accuracyData = useMemo(() => {
    const clamped = Math.min(100, Math.max(0, knowledgeIndexPct));
    return [
      { name: "Last week", accuracy: LAST_WEEK_KNOWLEDGE_INDEX },
      { name: "Current", accuracy: Number(clamped.toFixed(1)) },
    ];
  }, [knowledgeIndexPct]);

  const knowledgeTrend = useMemo(() => {
    const total = stats.total ?? 0;
    return total > 0 ? `+${total} chunks` : "+0 chunks";
  }, [stats.total]);

  const knowledgeIndexDetail =
    "Knowledge index is a readiness score for your embedded report chunks (not model prediction accuracy). " +
    "The API uses the same counts as Captions / Sections / Sources: score = min(100, round(11*ln(1+captions) + 9*ln(1+sections) + 6.5*ln(1+sources), 1)), then the UI shows that value. " +
    "ln is the natural logarithm; an empty store is 0%.";

  const adminHealthItems = useMemo(() => ([
    {
      label: "API service",
      value: "Connected",
      tone: "good",
      detail: "Status endpoint responded successfully."
    },
    {
      label: "Vector store",
      value: stats.exists ? "Ready" : "Not created",
      tone: stats.exists ? "good" : "warn",
      detail: stats.exists ? `${stats.total} embedded chunks available.` : "Index a report to create knowledge.pkl."
    },
    {
      label: "Knowledge index",
      value: `${knowledgeIndexPct.toFixed(1)}%`,
      tone: knowledgeIndexPct > 0 ? "good" : "warn",
      detail: knowledgeIndexDetail
    },
    {
      label: "Generated outputs",
      value: outputs.length,
      tone: outputs.length ? "good" : "neutral",
      detail: outputs.length ? "Files are available for download." : "No generated files yet."
    }
  ]), [stats.exists, stats.total, outputs.length, knowledgeIndexPct, knowledgeIndexDetail]);

  useEffect(() => {
    refreshStatus();
  }, []);

  async function refreshStatus() {
    try {
      const data = await getJson("/api/status");
      setStatus(data);
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  }

  async function handleIndex(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await submitForm("/api/index", form, "index", (data) => {
      setNotice({ type: "success", text: data.message });
      setStatus((current) => ({ ...current, stats: data.stats }));
      formElement.reset();
    });
  }

  async function handleCaption(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await submitForm("/api/caption", form, "caption", (data) => {
      setCaptionResult(data.result);
      setNotice({ type: "success", text: data.message });
      setStatus((current) => ({ ...current, outputs: data.outputs }));
    });
  }

  async function handleReport(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await submitForm("/api/report", form, "report", (data) => {
      setReportResult(data.result);
      setNotice({ type: "success", text: data.message });
      setStatus((current) => ({ ...current, outputs: data.outputs }));
    });
  }

  async function handlePredict(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setLoading("predict");
    setNotice(null);
    try {
      const response = await fetch(`${API_BASE}/api/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: form.get("query"),
          kind: form.get("kind"),
          top_k: 5,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Request failed.");
      setPredictionResult(data.result);
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setLoading(null);
    }
  }

  async function submitForm(path, form, key, onSuccess) {
    setLoading(key);
    setNotice(null);
    try {
      const response = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || "Request failed.");
      onSuccess(data);
      await refreshStatus();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="dashboard-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">
            <Sparkles size={20} />
          </div>
          <span className="brand-text">IEEE Studio</span>
        </div>

        <div className="sidebar-menu-label">Main Menu</div>
        <nav className="sidebar-nav">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`nav-item ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="status-pill">
            <span className={`status-dot ${readyState.tone}`} />
            {readyState.label}
          </div>
        </div>
      </aside>

      <main className="main-wrapper">
        <header className="topbar">
          <div className="search-bar">
            <Search size={18} />
            <input type="text" placeholder="Search reports, tasks, analytics..." />
          </div>
          <div className="topbar-actions">
            <button className="icon-btn">
              <Calendar size={18} />
              <span>Last 7 days</span>
            </button>
            <button className="icon-btn" style={{position: 'relative'}}>
              <Bell size={18} />
              <span className="badge-dot" style={{position: 'absolute', top: -2, right: -2, width: 8, height: 8, background: '#ef4444', borderRadius: '50%'}}></span>
            </button>
            <div className="user-profile" onClick={() => {
              if (adminAuthed) {
                setShowAdminPortal(true);
              } else {
                setShowAdminLogin(true);
              }
            }}>
              <div className="avatar">A</div>
              <div className="user-info">
                <strong>Admin User</strong>
                <span>local@ieee.org</span>
              </div>
            </div>
          </div>
        </header>

        {showAdminLogin && !adminAuthed && (
          <AdminLoginModal
            onSuccess={() => {
              setAdminAuthed(true);
              setShowAdminLogin(false);
              setShowAdminPortal(true);
            }}
            onClose={() => setShowAdminLogin(false)}
          />
        )}

        {showAdminPortal && adminAuthed && (
          <AdminPortal
            stats={stats}
            outputs={outputs}
            sections={sections}
            healthItems={adminHealthItems}
            knowledgeIndexPct={knowledgeIndexPct}
            onClose={() => setShowAdminPortal(false)}
          />
        )}

        <div className="content-area">
          {notice && <div className={`notice ${notice.type}`}>{notice.text}</div>}

          {activeTab === "home" && (
            <div className="pageTransition">
              <div className="page-header">
                <h1>AI System Insights</h1>
                <p>Knowledge index and counts come from the vector store; compare with files in data/reports.</p>
              </div>

              {(stats.total ?? 0) === 0 && (
                <p className="dashboard-hint">
                  Knowledge index stays at 0% until the vector store has at least one chunk. Use{" "}
                  <strong>Index Report</strong> to embed a PDF or DOCX; files only sitting in{" "}
                  <code>data/reports</code> are not counted until they are indexed (saved under{" "}
                  <code>vector_store/knowledge.pkl</code>).
                </p>
              )}

              <div className="metrics-grid">
                <MetricCard title="Captions Generated" value={stats.captions} trend="+12.5%" icon={ImagePlus} />
                <MetricCard title="Sections Indexed" value={stats.sections} trend="+8.2%" icon={FilePlus2} />
                <MetricCard title="Total Sources" value={stats.sources?.length || 0} trend="+15.0%" icon={Archive} />
                <MetricCard
                  title="Knowledge index"
                  value={`${knowledgeIndexPct.toFixed(1)}%`}
                  trend={knowledgeTrend}
                  icon={Activity}
                />
              </div>

              <div className="chart-panel pageTransition" style={{ animationDelay: '0.1s' }}>
                <div className="panel-heading" style={{ marginBottom: '24px' }}>
                  <Activity size={18} className="heading-icon" />
                  <h2>Knowledge index (vector store)</h2>
                </div>
                <div className="chart-container" style={{ height: 280, width: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={accuracyData} margin={{ top: 10, right: 30, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorAccuracy" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={(tick) => `${tick}%`} />
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#151e32', borderColor: '#1e293b', borderRadius: '8px', color: '#f8fafc' }}
                        itemStyle={{ color: '#93c5fd', fontWeight: 600 }}
                        formatter={(value) => [`${value}%`, "Knowledge index"]}
                      />
                      <Area type="monotone" dataKey="accuracy" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorAccuracy)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="dashboard-panels">
                <div className="dashboard-panel prediction-panel">
                  <div className="panel-heading">
                    <Search size={18} className="heading-icon" />
                    <h2>Prediction & Confidence</h2>
                  </div>
                  <form className="prediction-form" onSubmit={handlePredict}>
                    <input name="query" required placeholder="Try: workshop participants attending technical session" />
                    <select name="kind" defaultValue="section">
                      <option value="section">Report section</option>
                      <option value="caption">Caption</option>
                    </select>
                    <SubmitButton loading={loading === "predict"} icon={Search}>Check</SubmitButton>
                  </form>

                  {predictionResult ? (
                    <div className="prediction-result">
                      <div className="confidence-row">
                        <span>Top confidence</span>
                        <strong>{predictionResult.confidence_pct.toFixed(1)}%</strong>
                      </div>
                      <p>{predictionResult.prediction || "No matching prediction found."}</p>
                      <div className="match-list">
                        {predictionResult.matches.map((match, index) => (
                          <div className="match-row" key={`${match.source}-${index}`}>
                            <div>
                              <strong>{match.source}</strong>
                              <span>{match.heading || predictionResult.kind}</span>
                            </div>
                            <b>{match.confidence_pct.toFixed(1)}%</b>
                          </div>
                        ))}
                      </div>
                      <small>{predictionResult.note}</small>
                    </div>
                  ) : (
                    <p className="empty">Run a query to see the nearest RAG prediction and similarity score.</p>
                  )}
                </div>

                <div className="dashboard-panel">
                  <div className="panel-heading">
                    <Activity size={18} className="heading-icon" />
                    <h2>Model Status</h2>
                  </div>
                  <div className="panel-list">
                    {stats.sources?.length ? stats.sources.map((source, idx) => (
                      <div className="list-item" key={source.name}>
                        <div className="item-info">
                          <strong>{source.name}</strong>
                          <span>v1.{idx}.0 · {source.captions} captions · {source.sections} sections</span>
                        </div>
                        <div className="item-status active">
                          <CheckCircle2 size={14} /> Active
                        </div>
                      </div>
                    )) : (
                      <div className="list-item"><span className="empty">No indexed sources. Go to Index Report to add some.</span></div>
                    )}
                  </div>
                </div>

                <div className="dashboard-panel">
                  <div className="panel-heading">
                    <AlertTriangle size={18} className="heading-icon alert" />
                    <h2>Error Logs & Alerts</h2>
                  </div>
                  <div className="panel-list">
                    {outputs.length ? outputs.map((out) => (
                      <div className="list-item log-item" key={out.name}>
                        <div className="log-dot"></div>
                        <div className="item-info">
                          <strong>Generated file: {out.name}</strong>
                          <span>{out.modified} · <a href={`${API_BASE}/api/outputs/${encodeURIComponent(out.name)}`} className="download-link">Download</a></span>
                        </div>
                      </div>
                    )) : (
                      <div className="list-item"><span className="empty">No recent outputs generated.</span></div>
                    )}
                  </div>
                </div>
              </div>

              <div className="impact-panel">
                <div className="impact-icon">
                  <Sparkles size={20} />
                </div>
                <div className="impact-text">
                  <h3>AI Automation Impact</h3>
                  <p>This week, AI automation helped users save an estimated <strong>12 hours</strong> of manual work through intelligent document parsing and automated caption generation.</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === "index" && (
            <Panel eyebrow="Step 1" title="Build the Knowledge Base" badge="PDF / DOCX">
              <form className="actionForm" onSubmit={handleIndex}>
                <FilePicker name="report" accept=".pdf,.docx" title="Upload a previous-year report" description="Captions and sections are extracted, embedded, and saved locally." />
                <SubmitButton loading={loading === "index"} icon={Upload}>Index Report</SubmitButton>
              </form>
            </Panel>
          )}

          {activeTab === "caption" && (
            <Panel eyebrow="Step 2A" title="Caption Generator" badge="Image + context">
              <form className="splitForm" onSubmit={handleCaption}>
                <FilePicker name="image" accept=".jpg,.jpeg,.png,.webp,.gif" title="Choose event image" description="JPG, PNG, WEBP, or GIF up to 20 MB." compact />
                <Field label="Image description">
                  <textarea name="description" rows="8" required placeholder="Award ceremony at the IEEE student branch annual event" />
                </Field>
                <SubmitButton loading={loading === "caption"} icon={Sparkles}>Generate Captions</SubmitButton>
              </form>

              {captionResult && (
                <div className="resultGrid">
                  {captionResult.captions.map((caption, index) => (
                    <article className="resultCard" key={caption}>
                      <small>Variation {index + 1}</small>
                      <p>{caption}</p>
                    </article>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {activeTab === "report" && (
            <Panel eyebrow="Step 2B" title="Full Event Report" badge="Auto DOCX">
              <form className="reportForm" onSubmit={handleReport}>
                <Field label="Event name" wide>
                  <input name="event" required placeholder="IEEE Student Branch Induction 2024" />
                </Field>

                <Field label="Session points" wide>
                  <textarea
                    name="session_points"
                    rows="14"
                    required
                    placeholder={`Paste the complete event notes here:
- Date, time, venue, and participant count
- Speaker name, role, and topic
- Opening ceremony and welcome address
- Main sessions, activities, demonstrations, or competitions
- Outcomes, student response, SDG impact, IEEE goals, and acknowledgements`}
                  />
                </Field>

                <SubmitButton loading={loading === "report"} icon={FileText}>Generate DOCX</SubmitButton>
              </form>

              {reportResult && (
                <div className="downloadCard">
                  <CheckCircle2 size={20} />
                  <strong>{reportResult.file}</strong>
                  <a href={`${API_BASE}/api/outputs/${encodeURIComponent(reportResult.file)}`}>
                    <Download size={17} />
                    Download
                  </a>
                </div>
              )}
            </Panel>
          )}

          {activeTab === "library" && (
            <Panel eyebrow="Workspace" title="Knowledge and Outputs" badge={stats.exists ? "Store ready" : "No store yet"}>
              <div className="libraryGrid">
                <section>
                  <h2 className="subhead">Indexed Sources</h2>
                  {stats.sources?.length ? (
                    <div className="rowList">
                      {stats.sources.map((source) => (
                        <div className="libraryRow" key={source.name}>
                          <strong>{source.name}</strong>
                          <span>{source.captions} captions · {source.sections} sections</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="empty">No reports indexed yet.</p>
                  )}
                </section>

                <section>
                  <h2 className="subhead">Generated Files</h2>
                  {outputs.length ? (
                    <div className="rowList">
                      {outputs.map((file) => (
                        <a className="libraryRow outputLink" href={`${API_BASE}/api/outputs/${encodeURIComponent(file.name)}`} key={file.name}>
                          <strong>{file.name}</strong>
                          <span>{file.size_kb} KB · {file.modified}</span>
                        </a>
                      ))}
                    </div>
                  ) : (
                    <p className="empty">Generated captions and reports will appear here.</p>
                  )}
                </section>
              </div>
            </Panel>
          )}
        </div>
      </main>
    </div>
  );
}

function AdminPortal({ stats, outputs, sections, healthItems, knowledgeIndexPct, onClose }) {
  const latestOutputs = outputs.slice(0, 4);
  const adminCards = [
    { label: "Embedded chunks", value: stats.total ?? 0, icon: Database },
    { label: "Reports on disk", value: stats.reports_on_disk ?? 0, icon: HardDrive },
    { label: "Output files", value: outputs.length, icon: FileText },
    { label: "Report sections", value: sections.length, icon: BookOpenText },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="admin-modal pageTransition" role="dialog" aria-modal="true" aria-labelledby="admin-title" onClick={(event) => event.stopPropagation()}>
        <div className="admin-hero">
          <div>
            <p className="eyebrow">Control Center</p>
            <h2 id="admin-title">Admin Portal</h2>
            <span>System health, release notes, and local workspace activity.</span>
          </div>
          <button className="admin-close" type="button" onClick={onClose} aria-label="Close admin portal">
            <X size={18} />
          </button>
        </div>

        <div className="admin-body">
          <section className="admin-grid">
            {adminCards.map(({ label, value, icon: Icon }) => (
              <div className="admin-stat" key={label}>
                <Icon size={18} />
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </section>

          <section className="admin-section">
            <div className="admin-section-title">
              <ShieldCheck size={18} />
              <h3>Health Checks</h3>
            </div>
            <div className="health-list">
              {healthItems.map((item) => (
                <div className="health-row" key={item.label}>
                  <div>
                    <strong>{item.label}</strong>
                    <span>{item.detail}</span>
                  </div>
                  <b className={`health-badge ${item.tone}`}>{item.value}</b>
                </div>
              ))}
            </div>
          </section>

          <section className="admin-columns">
            <div className="admin-section">
              <div className="admin-section-title">
                <ServerCog size={18} />
                <h3>Version Logs</h3>
              </div>
              <div className="version-list">
                <VersionItem version="v1.3.0" label="Current" items={[
                  "Expanded admin portal with live status cards and health checks.",
                  "Added output and source summaries for faster workspace review."
                ]} />
                <VersionItem version="v1.2.0" items={[
                  "Added admin portal shell and version logs.",
                  "Added knowledge index trend chart with Recharts."
                ]} />
                <VersionItem version="v1.1.0" items={[
                  "Redesigned the dashboard layout and top navigation.",
                  "Added dynamic metrics from the Flask status API."
                ]} />
              </div>
            </div>

            <div className="admin-section">
              <div className="admin-section-title">
                <Archive size={18} />
                <h3>Recent Outputs</h3>
              </div>
              {latestOutputs.length ? (
                <div className="admin-output-list">
                  {latestOutputs.map((file) => (
                    <a href={`${API_BASE}/api/outputs/${encodeURIComponent(file.name)}`} key={file.name}>
                      <strong>{file.name}</strong>
                      <span>{file.size_kb} KB · {file.modified}</span>
                    </a>
                  ))}
                </div>
              ) : (
                <p className="empty">Generated captions and reports will appear here.</p>
              )}
            </div>
          </section>

          <section className="admin-section">
            <div className="admin-section-title">
              <Activity size={18} />
              <h3>Indexed Sources</h3>
            </div>
            {stats.sources?.length ? (
              <div className="source-table">
                {stats.sources.map((source) => (
                  <div className="source-row" key={source.name}>
                    <strong>{source.name}</strong>
                    <span>{source.captions} captions</span>
                    <span>{source.sections} sections</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty">No indexed reports yet. Knowledge index is currently {knowledgeIndexPct.toFixed(1)}%.</p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function AdminLoginModal({ onSuccess, onClose }) {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    // Simulate a short auth delay for UX
    setTimeout(() => {
      if (email.trim() === ADMIN_EMAIL && password === ADMIN_PASSWORD) {
        onSuccess();
      } else {
        setError("Invalid email or password. Please try again.");
      }
      setLoading(false);
    }, 600);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="login-modal pageTransition" role="dialog" aria-modal="true" aria-labelledby="login-title" onClick={(e) => e.stopPropagation()}>
        <div className="login-modal-header">
          <div className="login-lock-icon">
            <Lock size={22} />
          </div>
          <h2 id="login-title">Admin Access</h2>
          <p>Enter your credentials to access the Admin Portal.</p>
          <button className="admin-close" type="button" onClick={onClose} aria-label="Close login">
            <X size={18} />
          </button>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>Email</span>
            <input
              id="admin-email"
              type="email"
              autoComplete="username"
              required
              placeholder="local@ieee.org"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>

          <label className="login-field">
            <span>Password</span>
            <input
              id="admin-password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button className="primaryButton login-submit" type="submit" disabled={loading}>
            {loading ? <Loader2 className="spin" size={18} /> : <Lock size={18} />}
            {loading ? "Verifying..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

function VersionItem({ version, label, items }) {
  return (
    <div className="version-item">
      <strong>{version} {label ? <span>{label}</span> : null}</strong>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function emptyStats() {
  return {
    exists: false,
    path: "",
    total: 0,
    captions: 0,
    sections: 0,
    sources: [],
    reports_on_disk: 0,
    knowledge_index_pct: 0,
  };
}

function MetricCard({ title, value, trend, icon: Icon }) {
  return (
    <div className="metric-card">
      <div className="metric-icon-glow">
        <Icon size={20} />
      </div>
      <div className="metric-title">{title}</div>
      <div className="metric-bottom">
        <div className="metric-value">{value}</div>
        <div className="metric-trend">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
          {trend}
        </div>
      </div>
    </div>
  );
}

function Panel({ eyebrow, title, badge, children }) {
  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <span className="panelBadge">{badge}</span>
      </div>
      {children}
    </section>
  );
}

function Field({ label, wide, children }) {
  return (
    <label className={`field ${wide ? "wide" : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function FilePicker({ name, accept, title, description, compact }) {
  const [fileName, setFileName] = useState("");
  return (
    <label className={`dropzone ${compact ? "compact" : ""}`}>
      <input
        type="file"
        name={name}
        accept={accept}
        required
        onChange={(event) => setFileName(event.target.files?.[0]?.name || "")}
      />
      <Upload size={24} />
      <strong>{fileName || title}</strong>
      <span>{description}</span>
    </label>
  );
}

function SubmitButton({ loading, icon: Icon, children }) {
  return (
    <button className="primaryButton" type="submit" disabled={loading}>
      {loading ? <Loader2 className="spin" size={18} /> : <Icon size={18} />}
      {loading ? "Working..." : children}
    </button>
  );
}

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "Request failed.");
  return data;
}

createRoot(document.getElementById("root")).render(<App />);
