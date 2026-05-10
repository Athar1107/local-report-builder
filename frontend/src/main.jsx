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
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";

const tabs = [
  { id: "index", label: "Index", icon: FilePlus2 },
  { id: "caption", label: "Captions", icon: ImagePlus },
  { id: "report", label: "Report", icon: BookOpenText },
  { id: "library", label: "Library", icon: Archive },
];

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

function App() {
  const [activeTab, setActiveTab] = useState("index");
  const [status, setStatus] = useState({ stats: emptyStats(), outputs: [], sections: defaultSections });
  const [notice, setNotice] = useState(null);
  const [loading, setLoading] = useState(null);
  const [captionResult, setCaptionResult] = useState(null);
  const [reportResult, setReportResult] = useState(null);

  const sections = status.sections?.length ? status.sections : defaultSections;
  const stats = status.stats || emptyStats();
  const outputs = status.outputs || [];

  const readyState = useMemo(() => {
    if (stats.total > 0) return { label: "Knowledge store ready", tone: "ready" };
    return { label: "Index a report to begin", tone: "waiting" };
  }, [stats.total]);

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
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">IR</div>
          <div>
            <strong>IEEE Report Studio</strong>
            <span>Local RAG workspace</span>
          </div>
        </div>

        <nav className="navTabs" aria-label="Workspace">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                className={`navTab ${activeTab === tab.id ? "active" : ""}`}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                <Icon size={19} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="storeCard">
          <span className={`statusDot ${readyState.tone}`} />
          <div>
            <strong>{readyState.label}</strong>
            <span>{stats.captions} captions · {stats.sections} sections</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Fully local · Ollama powered</p>
            <h1>Generate IEEE-ready captions and reports from your branch archive.</h1>
          </div>
          <div className="metrics" aria-label="Project metrics">
            <Metric value={stats.captions} label="Captions" />
            <Metric value={stats.sections} label="Sections" />
            <Metric value={outputs.length} label="Outputs" />
          </div>
        </header>

        {notice && <div className={`notice ${notice.type}`}>{notice.text}</div>}

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
          <Panel eyebrow="Step 2B" title="Full Event Report" badge="DOCX output">
            <form className="reportForm" onSubmit={handleReport}>
              <Field label="Event name" wide>
                <input name="event" required placeholder="IEEE Student Branch Induction 2024" />
              </Field>

              <div className="sectionGrid">
                {sections.map(([key, label, help]) => (
                  <Field label={label} key={key}>
                    <textarea name={key} rows="5" placeholder={help} />
                  </Field>
                ))}
              </div>

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
                  <p className="emptyState">No reports indexed yet.</p>
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
                  <p className="emptyState">Generated captions and reports will appear here.</p>
                )}
              </section>
            </div>
          </Panel>
        )}
      </main>
    </div>
  );
}

function emptyStats() {
  return { exists: false, total: 0, captions: 0, sections: 0, sources: [] };
}

function Metric({ value, label }) {
  return (
    <div className="metric">
      <span>{value}</span>
      <small>{label}</small>
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
