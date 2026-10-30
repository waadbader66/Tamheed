import { FormEvent, useEffect, useRef, useState } from "react";
import { api, fmtDate } from "./api";
import { Bar, Card, Empty, Md, Pill, Ring, Shell } from "./ui";

function useRoute() {
  const [h, setH] = useState(location.hash);
  useEffect(() => { const f = () => setH(location.hash); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return h.replace(/^#\/?/, "").split("?")[0].split("/");
}

export function EmployeeApp({ user, onLogout }: { user: any; onLogout: () => void }) {
  const parts = useRoute();
  const page = parts[0] === "me" ? parts[1] || "home" : "home";
  const [w, setW] = useState<any>(null);
  const [err, setErr] = useState("");
  const [chatOpen, setChatOpen] = useState(false);
  const load = () => api("/me/workspace").then(setW).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  useEffect(() => {  // while the agent is reviewing/re-planning, refresh so its update appears by itself
    if (!w?.agent_working) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [w?.agent_working]);
  const p = w?.progress || {};
  const nav = [
    { key: "home", label: "Dashboard", icon: "⌂" },
    { key: "tasks", label: "Onboarding tasks", icon: "✓", badge: p.tasks_total ? `${p.tasks_done}/${p.tasks_total}` : undefined },
    { key: "responsibilities", label: "Responsibilities", icon: "◎" },
    { key: "training", label: "Training & courses", icon: "▶", badge: p.training_total ? `${p.training_done}/${p.training_total}` : undefined },
    { key: "exercise", label: "Practical exercise", icon: "✎", badge: w?.exercise ? (w.exercise.status === "assessed" ? `${w.exercise.score}%` : w.exercise.status === "open" ? "new" : undefined) : undefined },
    { key: "assistant", label: "AI assistant", icon: "✦" },
  ];
  return (
    <Shell scope="My onboarding" nav={nav} active={page} onNav={(k) => (location.hash = `/me/${k}`)} user={user} onLogout={onLogout}>
      {err && <div className="err">{err}</div>}
      {!w ? <div className="loading">Loading your workspace…</div> : <>
        {page === "home" && <Home w={w} reload={load} />}
        {page === "tasks" && <Tasks w={w} reload={load} />}
        {page === "responsibilities" && <Responsibilities w={w} reload={load} />}
        {page === "training" && <Training w={w} reload={load} />}
        {page === "assistant" && <Assistant full first={w.employee.first_name} />}
        {page === "exercise" && <PracticalExercise reloadWorkspace={load} />}
      </>}
      {page !== "assistant" && w && <>
        <button className="fab" onClick={() => setChatOpen(true)} aria-label="Open assistant">✦ Ask</button>
        {chatOpen && <div className="drawer"><div className="drawer-h"><b>Onboarding assistant</b><button className="ghost sm" onClick={() => setChatOpen(false)}>Close</button></div><Assistant first={w.employee.first_name} /></div>}
      </>}
    </Shell>
  );
}

function Home({ w, reload }: { w: any; reload: () => void }) {
  const e = w.employee, p = w.progress;
  const watchTask = w.tasks.find((t: any) => t.title.startsWith("Watch your personalised"));
  const onEnded = async () => { if (watchTask && watchTask.status === "pending") { await api(`/me/tasks/${watchTask.id}/submit`, { body: {} }); reload(); } };
  const next = [...w.tasks.filter((t: any) => t.status === "pending" && t.owner === "employee").map((t: any) => ({ k: "tasks", t: t.title, s: `Due ${fmtDate(t.due_date)}` })),
    ...w.training.filter((t: any) => t.status !== "completed").map((t: any) => ({ k: "training", t: t.title, s: t.priority }))].slice(0, 3);
  return (
    <div className="stack">
      <div className="welcome">
        <div>
          <div className="eyebrow">Welcome to Rimal</div>
          <h1>Welcome, {e.first_name}!</h1>
          <p>{e.title} · {e.department}{e.project ? ` · ${e.project.name}` : ""}</p>
          <div className="row wrap"><Pill tone="light">Manager: {e.manager?.name}</Pill><Pill tone="light">Starts {fmtDate(e.start_date)}</Pill></div>
        </div>
        <Ring value={p.percent} label="complete" />
      </div>
      <Card title="Your personalised welcome video" action={w.video && <span className="sub">{w.video.meta.duration}s · made for you</span>}>
        {w.video ? <VideoPlayer onEnded={onEnded} /> : <Empty>Your video is being prepared.</Empty>}
      </Card>
      {w.completed_at && (
        <div className="notice done celebrate">
          <span className="notice-i">🎉</span>
          <div className="grow"><b>You've completed your onboarding!</b>
            <div className="sub">Every task, responsibility, mandatory course and your practical exercise — done. Welcome to the team for real, {e.first_name}.</div></div>
        </div>
      )}
      {(w.updates?.length > 0 || w.agent_working) && (
        <Card title="Updates from your onboarding agent" className="agent-updates">
          {w.agent_working && <div className="upd"><span className="upd-i">✦</span><div><b>Reviewing your progress…</b><div className="sub">This takes a few seconds.</div></div></div>}
          {w.updates.map((u: any) => (
            <div key={u.id} className="upd">
              <span className="upd-i">{u.kind === "plan-update" ? "🔄" : "✦"}</span>
              <div className="grow">
                <b>{u.kind === "plan-update" ? "Your plan was updated" : "Nice progress!"}</b>
                <div>{u.text}</div>
                {u.data?.changes?.length > 0 && <ul className="ev-list">{u.data.changes.slice(0, 6).map((c: string, i: number) => <li key={i}>{c}</li>)}</ul>}
                <div className="sub">{fmtDate(u.at)}</div>
              </div>
            </div>
          ))}
        </Card>
      )}
      <div className="stats">
        <ProgStat label="Onboarding tasks" a={p.tasks_done} b={p.tasks_total} go="tasks" />
        <ProgStat label="Responsibilities" a={p.resp_done} b={p.resp_total} go="responsibilities" />
        <ProgStat label="Training & courses" a={p.training_done} b={p.training_total} go="training" />
        <div className="stat"><b>{p.tasks_verified}</b><span>Tasks verified by HR</span></div>
      </div>
      <Card title="Up next">
        {next.length ? next.map((n, i) => <button key={i} className="nextrow" onClick={() => (location.hash = `/me/${n.k}`)}><span className="num">{i + 1}</span><div><b>{n.t}</b><div className="sub">{n.s}</div></div><span className="chev">›</span></button>)
          : <Empty>You're all caught up.</Empty>}
      </Card>
    </div>
  );
}

function VideoPlayer({ onEnded }: { onEnded: () => void }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div className="empty">The video couldn't load. <button className="ghost sm" onClick={() => setFailed(false)}>Try again</button></div>;
  return <video className="vid" controls playsInline preload="metadata" src="/api/me/video#t=6" onEnded={onEnded} onError={() => setFailed(true)} />;
}

const ProgStat = ({ label, a, b, go }: any) => (
  <button className="stat clickable" onClick={() => (location.hash = `/me/${go}`)}><b>{a}<small>/{b}</small></b><span>{label}</span><Bar value={b ? (100 * a) / b : 0} /></button>
);

const SECTIONS = [
  { key: "paper", title: "Paperwork for HR", hint: "Complete these and tick them off — HR will verify.", cats: ["hr-paperwork"] },
  { key: "kit", title: "Your equipment & access", hint: "IT prepares these for you. Tick each one when you've received it and it works.", cats: ["hardware", "software", "access"] },
  { key: "start", title: "Getting started", hint: "Your first meetings and introductions.", cats: ["orientation"] },
];
const KIND: Record<string, string> = { hardware: "Hardware", software: "Software", access: "Access" };
const shortDate = (d?: string) => (d ? new Date(d).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "");

function Tasks({ w, reload }: { w: any; reload: () => void }) {
  const [busy, setBusy] = useState<number | null>(null);
  const toggle = async (t: any) => {
    if (t.status === "verified") return;
    setBusy(t.id);
    try { await api(`/me/tasks/${t.id}/${t.status === "pending" ? "submit" : "undo"}`, { body: {} }); await reload(); } catch {} finally { setBusy(null); }
  };
  const done = w.tasks.filter((t: any) => t.status !== "pending").length;
  return (
    <div className="stack">
      <div className="page-h"><h1>Onboarding tasks</h1><p>Tick each item when it's done.</p></div>
      <div className="tasks-sum">
        <div><b>{done}</b> of {w.tasks.length} done</div>
        <Bar value={(100 * done) / Math.max(1, w.tasks.length)} />
        <div className="legend"><span><i className="lg sub-d" /> Done</span><span><i className="lg ver-d" /> Verified by HR</span></div>
      </div>
      {SECTIONS.map((sec, si) => {
        const list = w.tasks.filter((t: any) => sec.cats.includes(t.category));
        if (!list.length) return null;
        const n = list.filter((t: any) => t.status !== "pending").length;
        return (
          <section key={sec.key} className="tsec">
            <div className="tsec-h">
              <span className="tsec-n">{si + 1}</span>
              <div className="grow"><h3>{sec.title}</h3><div className="sub">{sec.hint}</div></div>
              <span className={"tsec-c" + (n === list.length ? " all" : "")}>{n}/{list.length}</span>
            </div>
            <div className="tlist">
              {list.map((t: any) => (
                <button key={t.id} className={"trow " + t.status} onClick={() => toggle(t)} disabled={busy === t.id || t.status === "verified"} title={t.reason}>
                  <span className="tbox">{t.status !== "pending" ? "✓" : ""}</span>
                  <span className="ttitle">{t.title}{KIND[t.category] && <span className="tkind">{KIND[t.category]}</span>}</span>
                  <span className="tmeta">{t.status === "verified" ? "Verified ✓" : t.status === "submitted" ? "Done" : `Due ${shortDate(t.due_date)}`}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

const LVL: Record<string, [string, string, string]> = {
  independent: ["ok", "You can do this on your own", "Normal check-ins with your manager."],
  "light-guidance": ["warn", "Light guidance", "A mentor reviews your first deliverables."],
  mentoring: ["bad", "With a mentor", "You'll shadow your mentor before doing this alone."],
};

function Responsibilities({ w, reload }: { w: any; reload: () => void }) {
  const set = async (id: number, status: string) => { try { await api(`/me/responsibilities/${id}`, { body: { status } }); reload(); } catch {} };
  return (
    <div className="stack">
      <div className="page-h"><h1>Your first responsibilities</h1><p>What you'll own at the start, and how much support you'll get — based on your CV and experience.</p></div>
      {w.responsibilities.map((r: any) => (
        <Card key={r.id}>
          <div className="row between wrap"><h3 className="h3">{r.title}</h3><Pill tone={LVL[r.support_level][0]}>{LVL[r.support_level][1]}</Pill></div>
          <p className="muted">{r.detail}</p>
          <div className="why"><b>Why:</b> {r.rationale}</div>
          {r.evidence?.length > 0 && <div className="evidence">{r.evidence.map((e: any, i: number) => <div key={i}><Pill tone="ok">{e.skill}</Pill> <span className="sub">{e.source}{e.quote ? `: “${e.quote}”` : ""}</span></div>)}</div>}
          <div className="row between wrap" style={{ marginTop: 12 }}>
            {r.mentor ? <div className="mentor"><div className="avatar sm">{r.mentor.name.split(" ").map((s: string) => s[0]).slice(0, 2).join("")}</div><div><b>{r.mentor.name}</b><div className="sub">{r.mentor.title} · {r.mentor.email}</div></div></div> : <span className="sub">{LVL[r.support_level][2]}</span>}
            <div className="seg">{["not-started", "in-progress", "done"].map((s) => <button key={s} className={r.status === s ? "on" : ""} onClick={() => set(r.id, s)}>{s.replace("-", " ")}</button>)}</div>
          </div>
        </Card>
      ))}
    </div>
  );
}


function Training({ w, reload }: { w: any; reload: () => void }) {
  const [open, setOpen] = useState<any>(null);
  const set = async (id: number, status: string) => { try { await api(`/me/training/${id}`, { body: { status } }); reload(); } catch {} };
  const view = async (t: any) => {
    if (t.external) { window.open(t.url, "_blank", "noopener,noreferrer"); if (t.status === "not-started") set(t.id, "in-progress"); return; }
    try { setOpen(await api(`/me/courses/${t.code}`)); if (t.status === "not-started") set(t.id, "in-progress"); } catch {}
  };
  return (
    <div className="stack">
      <div className="page-h"><h1>Training & courses</h1><p>One mandatory course for everyone, plus optional courses your onboarding agent picked for your role, responsibilities and experience.</p></div>
      <div className="courses">
        {w.training.map((t: any) => (
          <Card key={t.id} className={"course " + t.status + (t.priority === "mandatory" ? " mand" : "")}>
            <div className="row between wrap">
              <div className="row tight"><Pill tone={t.priority === "mandatory" ? "bad" : "info"}>{t.priority === "mandatory" ? "Mandatory" : "Optional"}</Pill>
                <Pill tone="neutral">{t.external ? "External" : "Internal"}</Pill>
                {t.web_found && <Pill tone="ok">Found on the web by your agent</Pill>}</div>
              <span className="sub">{t.external ? t.provider : `${t.hours} h`}</span>
            </div>
            <h3 className="h3">{t.title}</h3>
            <p className="muted">{t.description}</p>
            <div className="why"><b>Why this course?</b> {t.rationale}</div>
            <div className="row between wrap" style={{ marginTop: 14 }}>
              <button className="primary sm" onClick={() => view(t)}>{t.external ? `Open on ${t.provider.split(" (")[0]} ↗` : "Open course"}</button>
              <div className="seg">{["not-started", "in-progress", "completed"].map((s) => <button key={s} className={t.status === s ? "on" : ""} onClick={() => set(t.id, s)}>{s.replace("-", " ")}</button>)}</div>
            </div>
          </Card>
        ))}
      </div>
      {open && <div className="modal" onClick={() => setOpen(null)}><div className="modal-c" onClick={(e) => e.stopPropagation()}><Md text={open.content_md} /><div className="row end"><button className="primary" onClick={() => setOpen(null)}>Close</button></div></div></div>}
    </div>
  );
}

function PracticalExercise({ reloadWorkspace }: { reloadWorkspace: () => void }) {
  const [d, setD] = useState<any>(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api("/me/exercise").then(setD).catch(() => {});
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (!d?.working) return;
    const t = setInterval(() => { load(); reloadWorkspace(); }, 3000);
    return () => clearInterval(t);
  }, [d?.working]);
  if (!d) return <div className="loading">Loading…</div>;
  const ex = d.exercise;
  if (!ex || (d.working && ex.status !== "submitted")) return (
    <div className="stack"><div className="page-h"><h1>Practical exercise</h1></div>
      <Card><div className="row"><span className="pulse" /> Your onboarding agent is designing a practical exercise for you…</div></Card></div>
  );
  const submit = async () => { setBusy(true); try { await api("/me/exercise/submit", { body: { answer } }); await load(); } catch {} finally { setBusy(false); } };
  const act = async (path: string) => { try { await api(path, { body: {} }); await load(); reloadWorkspace(); } catch {} };
  const ws = ex.worksheet || {};
  const openRef = (rid: string) => {
    const el = document.getElementById("ref-" + rid) as HTMLDetailsElement | null;
    if (el) { el.open = true; el.scrollIntoView({ behavior: "smooth", block: "center" }); }
  };
  const withRefs = (text: string) => text.split(/(\[[ED]\d+(?:,\s*[ED]\d+)*\])/g).map((part, i) =>
    /^\[[ED]\d+/.test(part) ? part.slice(1, -1).split(/,\s*/).map((rid) => (
      <button key={i + rid} className="ref-btn" onClick={() => openRef(rid)} title="Open this record">{rid}</button>))
      : <span key={i}>{part}</span>);
  return (
    <div className="stack narrow-page">
      <div className="page-h"><h1>Practical exercise</h1><p>A short real-world task based on your role — it helps your agent tailor how much support you get.</p></div>
      <Card>
        <div className="row between wrap"><Pill tone="info">For: {ex.responsibility}</Pill><span className="sub">~{ex.minutes} min{ex.attempt > 1 ? ` · attempt ${ex.attempt}` : ""}</span></div>
        <h2 className="ex-title">{ex.title}</h2>
        <p className="ex-text">{withRefs(ex.scenario)}</p>
        {ws.columns?.length > 0 && (
          <div className="ws-wrap"><table className="tbl ws">
            <thead><tr>{ws.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{ws.rows.map((r: string[], i: number) => <tr key={i} className="noclick">{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
          </table>{ws.notes && <div className="sub">{ws.notes}</div>}</div>
        )}
        <div className="why ex-task"><b>Your task</b><div>{withRefs(ex.task.replace(/\s+(?=\d\.\s)/g, "\n"))}</div>{ex.deliverable && <div className="sub" style={{ marginTop: 6 }}>Deliver: {ex.deliverable}</div>}</div>
        <div className="rubric">{ex.rubric.map((r: any) => <span key={r.criterion} className="rub"><b>{r.points}</b> {r.criterion}</span>)}</div>
      </Card>
      {ex.materials?.length > 0 && (
        <Card title="📎 Reference materials" action={<span className="sub">Everything you need for this exercise</span>}>
          {ex.materials.map((m: any) => (
            <details key={m.id} id={"ref-" + m.id} className="refdoc">
              <summary><span className="ref">{m.id}</span><span className="grow"><b>{m.title}</b>
                <span className="sub"> · {m.type === "email" ? `Email from ${m.from}, ${m.date}` : m.type.replace("-", " ")}</span>
                {m.location && <span className="where-s">{m.type === "email" ? "✉️" : "📁"} {m.location}</span>}</span><span className="fold-chev">›</span></summary>
              <div className="refdoc-b">
                {m.location && <div className="where">{m.type === "email" ? "✉️" : "📁"} <b>Where to find it:</b> {m.location}</div>}
                {m.type === "email" && <div className="sub">To: {m.to}</div>}<pre>{m.body}</pre></div>
            </details>
          ))}
        </Card>
      )}
      {ex.status === "open" && (
        <Card title="Your answer">
          <textarea rows={9} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Write your answer here…" style={{ width: "100%" }} />
          <div className="row end" style={{ marginTop: 12 }}><button className="primary" disabled={busy || answer.trim().length < 20} onClick={submit}>{busy ? "Submitting…" : "Submit"}</button></div>
        </Card>
      )}
      {ex.status === "submitted" && <Card><div className="row"><span className="pulse" /> Your agent is reviewing your answer…</div></Card>}
      {ex.status === "assessed" && (
        <Card title="Your result" action={<Pill tone="neutral">AI-assessed</Pill>}>
          <div className="result">
            <Ring value={ex.score || 0} label="score" size={110} />
            <div className="grow"><p style={{ marginTop: 0 }}>{ex.feedback}</p>
              {ex.breakdown?.criteria?.length > 0 && <div className="crit">{ex.breakdown.criteria.map((c: any) => (
                <div key={c.criterion} className="crit-row"><div className="row between"><b>{c.criterion}</b><span className="sub">{c.awarded}/{c.max}</span></div><Bar value={(100 * c.awarded) / Math.max(1, c.max)} />{c.comment && <div className="sub">{c.comment}</div>}</div>))}</div>}
              {ex.breakdown?.missed?.length > 0 && <div className="sub" style={{ marginTop: 10 }}><b>Worth another look:</b> {ex.breakdown.missed.join(" · ")}</div>}
            </div>
          </div>
          <div className="row end wrap" style={{ marginTop: 14 }}>
            {ex.mentor_review_requested ? <Pill tone="ok">Review requested with {ex.mentor}</Pill>
              : <button className="ghost" onClick={() => act("/me/exercise/review-request")}>Ask {ex.mentor || "my mentor"} to review</button>}
            <button className="primary" onClick={() => act("/me/exercise/retry")}>Try a new exercise</button>
          </div>
        </Card>
      )}
    </div>
  );
}

const SUGGEST = ["What should I do first this week?", "Can you explain my project?", "Why did we switch the 33 kV cable supplier?", "Who should I ask about relay protection?"];
const FOLLOW = ["Who should I ask about this?", "What should I do next?", "Explain it more simply"];
const TOOLN: Record<string, string> = { get_my_onboarding: "Checked your onboarding plan", search_company_records: "Looked through company emails & documents", find_people: "Searched the company directory", get_project: "Opened the project records" };

export function Assistant({ full, first }: { full?: boolean; first: string }) {
  const [msgs, setMsgs] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { api<any[]>("/me/chat").then(setMsgs); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);
  async function send(q: string) {
    if (!q.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", content: q, id: "tmp" + Date.now() }]); setText(""); setBusy(true);
    try { const r = await api("/me/chat", { body: { message: q } }); setMsgs((m) => [...m, r]); }
    catch (e: any) { setMsgs((m) => [...m, { role: "assistant", content: `Sorry — ${e.message}`, id: "err" + Date.now() }]); }
    finally { setBusy(false); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); send(text); };
  return (
    <div className={"chat" + (full ? " full" : "")}>
      {full && <div className="page-h"><h1>AI assistant</h1></div>}
      <div className="msgs">
        {msgs.length === 0 && <div className="hello"><div className="bot">✦</div><b>Hi {first}, welcome to Rimal! 👋</b><p>I'm your onboarding buddy. Ask me anything — your project, who to talk to, or why something was decided. No question is too small.</p>
          <div className="sugg">{SUGGEST.map((s) => <button key={s} onClick={() => send(s)}>{s}</button>)}</div></div>}
        {msgs.map((m, idx) => (
          <div key={m.id} className={"msg " + m.role}>
            {m.role === "assistant" && m.steps?.length > 0 && <div className="steps-trace">{m.steps.map((s: any, i: number) => <span key={i}>🔎 {TOOLN[s.tool] || s.tool}</span>)}</div>}
            <div className="bubble">{m.role === "assistant" ? <Md text={m.content} /> : m.content}</div>
            {m.role === "assistant" && idx === msgs.length - 1 && !busy && <div className="sugg small">{FOLLOW.map((f) => <button key={f} onClick={() => send(f)}>{f}</button>)}</div>}
          </div>
        ))}
        {busy && <div className="msg assistant"><div className="bubble typing"><i /><i /><i /></div></div>}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask anything about your work, projects or Rimal…" />
        <button className="primary" disabled={busy || !text.trim()}>Send</button>
      </form>
    </div>
  );
}
