import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, fmtDate, fmtTime } from "./api";
import { Bar, Card, Empty, Pill, Ring, Shell } from "./ui";

const NAV = [
  { key: "overview", label: "Onboarding progress", icon: "◔" },
  { key: "add", label: "Add employee", icon: "＋" },
  { key: "invitations", label: "Invitations", icon: "✉" },
  { key: "directory", label: "All employees", icon: "☰" },
  { key: "evaluation", label: "Evaluation", icon: "✓" },
];

function useRoute() {
  const [h, setH] = useState(location.hash);
  useEffect(() => { const f = () => setH(location.hash); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  const parts = h.replace(/^#\/?/, "").split("?")[0].split("/");
  return parts; // ["hr", page, id]
}

export function HrApp({ user, onLogout }: { user: any; onLogout: () => void }) {
  const parts = useRoute();
  const page = parts[0] === "hr" ? parts[1] || "overview" : "overview";
  const id = parts[2];
  const navKey = page === "prep" || page === "employee" || page === "edit" ? "overview" : page;
  return (
    <Shell scope="HR workspace" nav={NAV} active={navKey} onNav={(k) => (location.hash = `/hr/${k}`)} user={user} onLogout={onLogout}>
      {page === "add" && <AddEmployee />}
      {page === "edit" && <AddEmployee editId={id} />}
      {page === "prep" && <Preparation caseId={id} />}
      {page === "employee" && <EmployeeRecord id={id} />}
      {page === "invitations" && <Invitations />}
      {page === "directory" && <Directory />}
      {page === "evaluation" && <Evaluation />}
      {navKey === "overview" && page !== "prep" && page !== "employee" && page !== "edit" && <Overview />}
    </Shell>
  );
}

function usePoll<T>(path: string, ms = 4000): [T | null, () => void, string] {
  const [d, setD] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const load = () => api<T>(path).then((x) => { setD(x); setErr(""); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); const t = setInterval(load, ms); return () => clearInterval(t); }, [path]);
  return [d, load, err];
}

const caseTone: Record<string, string> = { ready: "ok", preparing: "info", failed: "bad" };
const invTone: Record<string, string> = { sent: "ok", failed: "bad", "waiting-sender-config": "warn", "blocked-not-allowlisted": "warn", prepared: "info" };
const invLabel: Record<string, string> = { sent: "Sent", failed: "Failed", "waiting-sender-config": "Waiting for sender setup", "blocked-not-allowlisted": "Not allowlisted", prepared: "Prepared" };

function hireStatus(h: any): [string, string] {
  if (h.case_status === "completed") return ["ok", "Onboarding complete ✓"];
  if (h.case_status === "failed") return ["bad", "Needs attention"];
  if (h.case_status === "preparing") return ["info", "Preparing…"];
  if (h.first_login) return ["info", "In progress"];
  return ["warn", "Invited"];
}

function Overview() {
  const [d, reload] = usePoll<any>("/hr/overview");
  if (!d) return <div className="loading">Loading…</div>;
  const ack = async (caseId: number) => { await api(`/hr/cases/${caseId}/ack`, { body: {} }).catch(() => {}); reload(); };
  return (
    <div className="stack narrow-page">
      <div className="row between wrap">
        <div className="page-h"><h1>Onboarding progress</h1></div>
        <button className="primary" onClick={() => (location.hash = "/hr/add")}>＋ Add employee</button>
      </div>
      {d.notices.map((n: any) => (
        <div key={n.case_id} className="notice">
          <span className="notice-i">🎉</span>
          <div className="grow"><b>{n.name} has completed onboarding!</b>
            <div className="sub">Every task, responsibility, mandatory course and the practical exercise are done.{n.graduates_on ? ` Moves to existing employees on ${fmtDate(n.graduates_on)}.` : ""}</div></div>
          <button className="ghost sm" onClick={() => (location.hash = `/hr/employee/${n.employee_id}`)}>View</button>
          <button className="link" onClick={() => ack(n.case_id)}>Dismiss</button>
        </div>
      ))}
      <div className="stats three">
        <Stat n={d.new_hires} l="New hires" accent />
        <Stat n={d.completed} l="Onboarding complete" />
        <Stat n={d.awaiting_verification} l="Waiting for your check" />
      </div>
      {d.hires.length === 0 ? <Empty>No new hires yet. Add an employee to start their onboarding.</Empty> : (
        <div className="hires">
          {d.hires.map((h: any) => {
            const [tone, label] = hireStatus(h);
            return (
              <button key={h.id} className="hire" onClick={() => (location.hash = h.case_status === "preparing" ? `/hr/prep/${h.case_id}` : `/hr/employee/${h.id}`)}>
                <span className="avatar">{h.name.split(" ").map((x: string) => x[0]).slice(0, 2).join("")}</span>
                <span className="hire-who"><b>{h.name}</b><span className="sub">{h.title} · starts {fmtDate(h.start_date)}</span></span>
                <Pill tone={tone}>{label}</Pill>
                <span className="hire-prog"><Bar value={h.progress.percent || 0} /><b>{h.progress.percent || 0}%</b></span>
                <span className="chev">›</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const Stat = ({ n, l, accent }: { n: number; l: string; accent?: boolean }) => <div className={"stat" + (accent ? " accent" : "")}><b>{n}</b><span>{l}</span></div>;

function AddEmployee({ editId }: { editId?: string }) {
  const [opt, setOpt] = useState<any>(null);
  const [f, setF] = useState<any>({ employee_code: "", full_name: "", email: "", role_id: "", department_id: "", manager_id: "", project_id: "", start_date: "", experience_years: "", experience_text: "", qualifications: "", responsibilities_text: "", extra_context: "" });
  const [cv, setCv] = useState<File | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [cvName, setCvName] = useState("");
  useEffect(() => { api("/hr/options").then(setOpt); }, []);
  useEffect(() => {
    if (!editId) return;
    api(`/hr/employees/${editId}`).then((d) => {
      const p = d.profile, s = (v: any) => (v === null || v === undefined ? "" : String(v));
      setF({ employee_code: p.code, full_name: p.name, email: p.email, role_id: s(p.role_id), department_id: s(p.department_id), manager_id: s(p.manager_id),
        project_id: s(p.project_id), start_date: s(p.start_date), experience_years: s(p.experience_years), experience_text: s(p.experience_text),
        qualifications: s(p.qualifications), responsibilities_text: s(p.responsibilities_text), extra_context: s(p.extra_context) });
      setCvName(d.cv_filename || "");
    });
  }, [editId]);
  const set = (k: string) => (e: any) => setF((x: any) => ({ ...x, [k]: e.target.value }));
  const onRole = (e: any) => {
    const r = opt.roles.find((r: any) => String(r.id) === e.target.value);
    setF((x: any) => ({ ...x, role_id: e.target.value, department_id: r ? String(r.department_id) : x.department_id }));
  };
  const managers = useMemo(() => (opt ? opt.managers.slice().sort((a: any, b: any) => (b.department_id === +f.department_id ? 1 : 0) - (a.department_id === +f.department_id ? 1 : 0)) : []), [opt, f.department_id]);
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr("");
    const req = ["employee_code", "full_name", "email", "role_id", "department_id", "manager_id", "start_date"];
    const miss = req.filter((k) => !String(f[k]).trim());
    if (miss.length) return setErr("Please complete: " + miss.map((k) => k.replace(/_id$/, "").replace(/_/g, " ")).join(", "));
    const fd = new FormData();
    if (editId) {
      ["role_id", "department_id", "manager_id", "project_id", "start_date", "experience_years", "experience_text", "qualifications", "responsibilities_text", "extra_context"]
        .forEach((k) => fd.append(k, String(f[k] ?? "")));
    } else {
      Object.entries(f).forEach(([k, v]) => { if (String(v).trim() !== "") fd.append(k, String(v)); });
    }
    if (cv) fd.append("cv", cv);
    setBusy(true);
    try {
      if (editId) {
        const r = await api(`/hr/employees/${editId}/update`, { form: fd });
        location.hash = r.changed ? `/hr/prep/${r.case_id}` : `/hr/employee/${editId}`;
      } else {
        const r = await api("/hr/employees", { form: fd }); location.hash = `/hr/prep/${r.case_id}`;
      }
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  if (!opt) return <div className="loading">Loading…</div>;
  return (
    <form className="stack" onSubmit={submit}>
      {editId && <BackLink />}
      {editId ? <div className="page-h"><h1>Edit {f.full_name}</h1><p>Changes to role, project, manager, background or responsibilities make the onboarding agent re-plan — completed work is kept.</p></div>
        : <div className="page-h"><h1>Add a new employee</h1><p>Saving starts the onboarding agent: it reads the CV, plans responsibilities and training, renders the video and sends the invitation.</p></div>}
      <Card title="Identity">
        <div className="grid3">
          <label>Employee ID *<input value={f.employee_code} onChange={set("employee_code")} placeholder="e.g. R-1042" disabled={!!editId} /></label>
          <label>Full name *<input value={f.full_name} onChange={set("full_name")} disabled={!!editId} /></label>
          <label>Email (becomes username) *<input type="email" value={f.email} onChange={set("email")} disabled={!!editId} /></label>
        </div>
      </Card>
      <Card title="Role & placement">
        <div className="grid3">
          <label>Job role *<select value={f.role_id} onChange={onRole}><option value="">Select…</option>{opt.roles.map((r: any) => <option key={r.id} value={r.id}>{r.title}</option>)}</select></label>
          <label>Department *<select value={f.department_id} onChange={set("department_id")}><option value="">Select…</option>{opt.departments.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
          <label>Start date *<input type="date" value={f.start_date} onChange={set("start_date")} /></label>
          <label>Manager *<select value={f.manager_id} onChange={set("manager_id")}><option value="">Select…</option>{managers.map((m: any) => <option key={m.id} value={m.id}>{m.name} — {m.title}</option>)}</select></label>
          <label>Project / team<select value={f.project_id} onChange={set("project_id")}><option value="">None yet</option>{opt.projects.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label>Years of experience<input type="number" min="0" max="50" value={f.experience_years} onChange={set("experience_years")} /></label>
        </div>
      </Card>
      <Card title="Background">
        <div className="grid2">
          <label>Previous experience<textarea rows={5} value={f.experience_text} onChange={set("experience_text")} placeholder="Previous employers, projects, achievements…" /></label>
          <label>Qualifications & skills<textarea rows={5} value={f.qualifications} onChange={set("qualifications")} placeholder="Degrees, certifications, tools…" /></label>
          <label>Key responsibilities (one per line)<textarea rows={5} value={f.responsibilities_text} onChange={set("responsibilities_text")} placeholder={"Leave empty to use the role's standard duties"} /></label>
          <label>Additional context<textarea rows={5} value={f.extra_context} onChange={set("extra_context")} placeholder="Anything else the onboarding should consider" /></label>
        </div>
        <label className="file">
          <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setCv(e.target.files?.[0] || null)} />
          <span className="file-box">{cv ? <>📄 <b>{cv.name}</b> · {(cv.size / 1024).toFixed(0)} KB</> : cvName ? <>Current CV: <b>{cvName}</b> <span className="sub">— upload a new one to replace it</span></> : <>Upload CV <span className="sub">(PDF, DOCX or TXT, max 5 MB)</span></>}</span>
        </label>
      </Card>
      {err && <div className="err" role="alert">{err}</div>}
      <div className="row end">{editId && <button type="button" className="ghost big" onClick={() => (location.hash = `/hr/employee/${editId}`)}>Cancel</button>}
        <button className="primary big" disabled={busy}>{busy ? "Saving…" : editId ? "Save changes" : "Save & start onboarding"}</button></div>
    </form>
  );
}

function Preparation({ caseId }: { caseId: string }) {
  const [d, reload] = usePoll<any>(`/hr/cases/${caseId}`, 1500);
  const [started] = useState(Date.now());
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 1000); return () => clearInterval(t); }, []);
  if (!d) return <div className="loading">Loading…</div>;
  const done = d.stages.filter((s: any) => s.status === "done").length;
  const failed = d.stages.some((s: any) => s.status === "failed");
  const ready = done === d.stages.length;
  const first = d.employee.name.split(" ")[0];
  const retry = async () => { await api(`/hr/cases/${caseId}/retry`, { body: {} }); reload(); };
  return (
    <div className="prep">
      <BackLink />
      <div className={"prep-hero" + (ready ? " done" : "")}>
        <div className="orbit"><i /><i /><i /><b>{ready ? "✓" : `${Math.round((100 * done) / d.stages.length)}%`}</b></div>
        <div>
          <h1>{ready ? `${first}'s workspace is ready` : failed ? "Preparation needs attention" : `Preparing ${first}'s onboarding…`}</h1>
          <p>{d.employee.title} · {d.employee.email}</p>
          {!ready && !failed && <p className="sub light">Live status from the onboarding pipeline · {Math.round((Date.now() - started) / 1000)}s on this page</p>}
        </div>
      </div>
      <div className="prep-grid">
      <Card title="Pipeline">
        <ol className="stages">
          {d.stages.map((s: any) => (
            <li key={s.key} className={s.status}>
              <span className="dot">{s.status === "done" ? "✓" : s.status === "failed" ? "!" : s.status === "running" ? "" : ""}</span>
              <div><b>{s.label}</b>{s.detail && <div className="sub">{s.detail}</div>}
                {s.status === "running" && s.key === "video" && <div className="sub">Rendering animation frames and narration — this takes about 2 minutes.</div>}</div>
              <span className="when">{s.finished_at ? fmtTime(s.finished_at) : s.status === "running" ? "working…" : ""}</span>
            </li>
          ))}
        </ol>
        {failed && <div className="row end"><button className="primary" onClick={retry}>Retry failed step</button></div>}
      </Card>
      <AgentFeed events={d.agent} live={!ready && !failed} source={d.plan_source} />
      </div>
      {ready && (
        <div className="row end">
          <button className="ghost" onClick={() => (location.hash = "/hr/invitations")}>View invitation status</button>
          <button className="primary" onClick={() => (location.hash = `/hr/employee/${d.employee.id}`)}>Open employee record</button>
        </div>
      )}
    </div>
  );
}

const EV: Record<string, [string, string]> = {
  thinking: ["💭", "thinking"], tool: ["🔧", "tool"], decision: ["✅", "decision"], guardrail: ["🛡️", "guardrail"],
  fallback: ["⚠️", "fallback"], warning: ["🚩", "warning for HR"], "plan-update": ["🔄", "plan update"], "next-step": ["➡️", "next step"],
};

function AgentFeed({ events, live, source, title = "Onboarding agent — live" }: { events: any[]; live?: boolean; source?: string; title?: string }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { if (live) end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [events?.length, live]);
  return (
    <Card title={<span className="row tight">{live && <span className="pulse" />}{title}</span>} action={source ? <span className="sub">{source}</span> : null} className="agent-card">
      {!events?.length ? <Empty>{live ? "The agent is starting…" : "No agent activity yet."}</Empty> : (
        <div className="feed">
          {events.map((e: any) => (
            <div key={e.id} className={"ev " + e.kind}>
              <span className="ev-i" title={EV[e.kind]?.[1]}>{EV[e.kind]?.[0] || "•"}</span>
              <div className="grow">
                <div className="ev-t">{e.text}</div>
                {e.data?.changes?.length > 0 && <ul className="ev-list">{e.data.changes.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul>}
              </div>
              <span className="ev-at">{fmtTime(e.at).split(", ").pop()}</span>
            </div>
          ))}
          <div ref={end} />
        </div>
      )}
    </Card>
  );
}

const lvl: Record<string, [string, string]> = { independent: ["ok", "Independent"], "light-guidance": ["warn", "Light guidance"], mentoring: ["bad", "Needs mentoring"] };

export const BackLink = () => <button className="backlink" onClick={() => (location.hash = "/hr/overview")}>← Onboarding progress</button>;

function Fold({ title, count, children, open }: { title: string; count?: number | string; children: any; open?: boolean }) {
  return (
    <details className="fold" open={open}>
      <summary><span>{title}</span>{count !== undefined && <span className="fold-c">{count}</span>}<span className="fold-chev">›</span></summary>
      <div className="fold-b">{children}</div>
    </details>
  );
}

function Attention({ items }: { items: any[] }) {
  const [all, setAll] = useState(false);
  return (
    <Card title={`Needs your attention (${items.length})`} className="attention">
      {all ? items : items.slice(0, 2)}
      {items.length > 2 && <button className="link" onClick={() => setAll(!all)}>{all ? "Show less" : `Show ${items.length - 2} more`}</button>}
    </Card>
  );
}

function ProgRow({ label, a, b, hint }: { label: string; a: number; b: number; hint?: string }) {
  return (
    <div className="progrow">
      <div className="row between"><b>{label}</b><span className="sub"><b>{a}</b> / {b}</span></div>
      <Bar value={b ? (100 * a) / b : 0} />
      {hint && <div className="sub">{hint}</div>}
    </div>
  );
}

function EmployeeRecord({ id }: { id: string }) {
  const [d, reload] = usePoll<any>(`/hr/employees/${id}`, 5000);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!d) return <div className="loading">Loading…</div>;
  const p = d.profile, pr = d.progress || {};
  const remove = async () => {
    setBusy(true); setErr("");
    try { await api(`/hr/employees/${id}`, { method: "DELETE" }); location.hash = "/hr/overview"; }
    catch (e: any) { setErr(e.message); setBusy(false); }
  };
  const verify = async (tid: number) => { await api(`/hr/tasks/${tid}/verify`, { body: {} }); reload(); };
  const failed = (d.stages || []).some((s: any) => s.status === "failed");
  const working = (d.stages || []).some((s: any) => s.status === "running" || s.status === "pending");
  const status = d.completed_at ? ["ok", "Onboarding complete ✓"] : failed ? ["bad", "Needs attention"] : working ? ["info", "Agent working…"] : ["ok", "Workspace ready"];
  const graduate = async () => { await api(`/hr/employees/${id}/graduate`, { body: {} }).catch(() => {}); reload(); };
  const inv = d.invitation;
  const invState = !inv ? "Not sent yet" : inv.password_changed_at ? "Signed in & password set" : inv.first_login_at ? "Signed in" : inv.status === "sent" ? "Invitation sent" : invLabel[inv.status] || inv.status;
  const events = d.agent || [];
  const lastRun = [...events].reverse().find((e: any) => e.kind === "decision" && !String(e.run).startsWith("review"))?.run;
  const warnings = events.filter((e: any) => e.kind === "warning" && e.run === lastRun);
  const waiting = (d.tasks || []).filter((t: any) => t.status === "submitted");
  const mentors = Array.from(new Set((d.responsibilities || []).map((r: any) => r.mentor?.name).filter(Boolean)));
  return (
    <div className="stack narrow-page">
      <BackLink />
      <div className="page-h row between wrap">
        <div><h1>{p.name}</h1><p>{p.title}{p.project ? ` · ${p.project.name}` : ""} · starts {fmtDate(p.start_date)}</p></div>
        {p.is_new_hire && <div className="row">
          <button className="ghost sm" onClick={() => (location.hash = `/hr/edit/${id}`)}>Edit</button>
          <button className="ghost sm danger-t" onClick={() => setConfirm(true)}>Delete</button>
        </div>}
      </div>
      {confirm && (
        <div className="modal" onClick={() => !busy && setConfirm(false)}>
          <div className="modal-c narrow" onClick={(e) => e.stopPropagation()}>
            <h2>Delete {p.name}?</h2>
            <p className="muted">This permanently removes their account, onboarding plan, tasks, training, video, CV, invitation and chat history. This can't be undone.</p>
            {err && <div className="err">{err}</div>}
            <div className="row end" style={{ marginTop: 18 }}>
              <button className="ghost" disabled={busy} onClick={() => setConfirm(false)}>Cancel</button>
              <button className="danger" disabled={busy} onClick={remove}>{busy ? "Deleting…" : "Delete permanently"}</button>
            </div>
          </div>
        </div>
      )}
      <div className="summary">
        <Ring value={pr.percent || 0} label="complete" size={130} />
        <div className="summary-mid">
          <div className="row wrap"><Pill tone={status[0]}>{status[1]}</Pill><Pill tone={inv?.password_changed_at ? "ok" : "neutral"}>{invState}</Pill></div>
          <ProgRow label="Onboarding tasks" a={pr.tasks_done || 0} b={pr.tasks_total || 0} hint={pr.tasks_verified ? `${pr.tasks_verified} verified by you` : undefined} />
          <ProgRow label="Responsibilities" a={pr.resp_done || 0} b={pr.resp_total || 0} />
          <ProgRow label="Training" a={pr.training_done || 0} b={pr.training_total || 0} hint={pr.mandatory_open ? "Mandatory course not finished yet" : undefined} />
        </div>
        <dl className="dl summary-people">
          <dt>Manager</dt><dd>{p.manager?.name || "—"}</dd>
          <dt>Mentor{mentors.length > 1 ? "s" : ""}</dt><dd>{mentors.join(", ") || "—"}</dd>
        </dl>
      </div>
      {d.completed_at && (
        <div className="notice done">
          <span className="notice-i">🎉</span>
          <div className="grow">{d.graduated_at
            ? <><b>Existing employee since {fmtDate(d.graduated_at)}</b><div className="sub">Completed onboarding on {fmtDate(d.completed_at)}.</div></>
            : <><b>Onboarding complete — {fmtDate(d.completed_at)}</b><div className="sub">Moves to existing employees automatically on {fmtDate(d.graduates_on)}.</div></>}</div>
          {!d.graduated_at && <button className="primary sm" onClick={graduate}>Move to existing now</button>}
        </div>
      )}
      {(waiting.length > 0 || warnings.length > 0 || failed) && !d.completed_at && (
        <Attention items={[
          ...(failed ? [<div key="f" className="att-row"><span>⚠️ A preparation step failed.</span><button className="primary sm" onClick={() => (location.hash = `/hr/prep/${d.case_id}`)}>Retry</button></div>] : []),
          ...waiting.map((t: any) => <div key={t.id} className="att-row"><span>✅ <b>{t.title}</b> — marked done</span><button className="primary sm" onClick={() => verify(t.id)}>Verify</button></div>),
          ...warnings.map((w: any) => <div key={w.id} className="att-row"><span>🚩 {w.text.replace(/^Please check: /, "")}</span></div>),
        ]} />
      )}
      <div className="folds">
        <Fold title="Onboarding tasks" count={`${pr.tasks_done || 0}/${pr.tasks_total || 0}`}>
          {(d.tasks || []).map((t: any) => (
            <div key={t.id} className="li row between">
              <div><b>{t.title}</b><div className="sub">{t.owner === "it" ? "IT" : t.owner === "hr" ? "HR" : "Employee"} · due {fmtDate(t.due_date)}</div></div>
              {t.status === "verified" ? <Pill tone="ok">Verified</Pill> : t.status === "submitted" ? <button className="primary sm" onClick={() => verify(t.id)}>Verify</button> : <Pill tone="neutral">Open</Pill>}
            </div>))}
        </Fold>
        <Fold title="Responsibilities & mentoring" count={(d.responsibilities || []).length}>
          {(d.responsibilities || []).map((r: any) => <div key={r.id} className="li"><div className="row between"><b>{r.title}</b><Pill tone={lvl[r.support_level][0]}>{lvl[r.support_level][1]}</Pill></div>
            <div className="sub">{r.rationale}</div>{r.mentor && <div className="sub">Mentor: {r.mentor.name}</div>}</div>)}
        </Fold>
        <Fold title="Training" count={`${pr.training_done || 0}/${pr.training_total || 0}`}>
          {(d.training || []).map((t: any) => <div key={t.id} className="li"><div className="row between"><b>{t.title}</b><Pill tone={t.status === "completed" ? "ok" : "neutral"}>{t.status.replace("-", " ")}</Pill></div>
            <div className="sub">{t.priority === "mandatory" ? "Mandatory" : "Optional"} · {t.external ? t.provider : "Rimal Academy"} — {t.rationale}</div></div>)}
        </Fold>
        {d.exercise && <Fold title="Practical exercise" count={d.exercise.status === "assessed" ? `${d.exercise.score}%` : d.exercise.status === "open" ? "not started" : "in review"}>
          <div className="li"><b>{d.exercise.title}</b><div className="sub">For “{d.exercise.responsibility}” · attempt {d.exercise.attempt} · {d.exercise.source}</div></div>
          {d.exercise.status === "assessed" && <div className="li"><div className="row between"><b>Score {d.exercise.score}%</b><Pill tone="neutral">AI-assessed</Pill></div>
            <div className="sub">{d.exercise.feedback}</div>{d.exercise.mentor_review_requested && <div className="sub">Employee asked {d.exercise.mentor} to review.</div>}</div>}
        </Fold>}
        <Fold title="More details">
          {d.analysis?.summary && <p className="agent-sum open">🤖 <b>Agent summary:</b> {d.analysis.summary}</p>}
          {d.video && <><h4 className="sub-h">Welcome video</h4>
            <video className="vid small" controls preload="metadata" src={`/api/hr/employees/${id}/video#t=6`} /></>}
          <h4 className="sub-h">Background</h4>
          <dl className="dl">
            <dt>Email</dt><dd>{p.email}</dd>
            <dt>Experience</dt><dd>{p.experience_text || "—"}</dd>
            <dt>Qualifications</dt><dd>{p.qualifications || "—"}</dd>
            <dt>CV</dt><dd>{d.cv_filename || "Not provided"}</dd>
          </dl>
          {d.analysis && <><h4 className="sub-h">Skills</h4><div className="skills">{d.analysis.skills.map((s: any) => (
            <div key={s.key} className={"skill " + s.status}><b>{s.name}</b><span>{s.status === "evidenced" ? `Shown — ${s.evidence[0].source}` : "Not shown yet"}</span>
              {s.evidence[0]?.quote && <q>{s.evidence[0].quote}</q>}</div>))}</div></>}
          {events.length > 0 && <><h4 className="sub-h">Agent activity log</h4>
            <AgentFeed events={events.filter((e: any) => e.kind !== "thinking")} source={d.plan_source} title="All agent decisions" /></>}
        </Fold>
      </div>
    </div>
  );
}

function Invitations() {
  const [list, reload] = usePoll<any[]>("/hr/invitations", 4000);
  const [msg, setMsg] = useState("");
  const [sending, setSending] = useState<number | null>(null);
  const resend = async (id: number) => {
    if (sending) return;
    setMsg(""); setSending(id);
    try { const r = await api(`/hr/invitations/${id}/resend`, { body: {} }); setMsg(`${r.name}: ${invLabel[r.status] || r.status}${r.detail ? " — " + r.detail : ""}`); reload(); }
    catch (e: any) { setMsg(e.message); } finally { setSending(null); }
  };
  if (!list) return <div className="loading">Loading…</div>;
  return (
    <div className="stack">
      <div className="page-h"><h1>Invitations</h1><p>Every invitation, its delivery status and what the new hire has done since.</p></div>
      {msg && <div className="note">{msg}</div>}
      <Card>
        {list.length === 0 ? <Empty>No invitations yet. They're created automatically when a workspace is ready.</Empty> : (
          <table className="tbl">
            <thead><tr><th>Employee</th><th>Sent to</th><th>Delivery</th><th>Link opened</th><th>Signed in</th><th>Password set</th><th /></tr></thead>
            <tbody>{list.map((i) => (
              <tr key={i.id} className="noclick">
                <td><b>{i.name}</b><div className="sub">{i.title}</div></td>
                <td>{i.to}<div className="sub">username: {i.username}</div></td>
                <td><Pill tone={invTone[i.status]}>{invLabel[i.status] || i.status}</Pill><div className="sub">{i.sent_at ? fmtTime(i.sent_at) : i.detail}</div></td>
                <td>{i.viewed_at ? <Pill tone="ok">{fmtTime(i.viewed_at)}</Pill> : <span className="sub">Not yet</span>}</td>
                <td>{i.first_login_at ? <Pill tone="ok">{fmtTime(i.first_login_at)}</Pill> : <span className="sub">Not yet</span>}</td>
                <td>{i.password_changed_at ? <Pill tone="ok">Done</Pill> : <span className="sub">Pending</span>}</td>
                <td>{!i.password_changed_at && <button className="ghost sm" disabled={sending !== null} onClick={() => resend(i.id)}>{sending === i.id ? "Sending…" : i.status === "sent" ? "Resend" : "Send now"}</button>}</td>
              </tr>))}</tbody>
          </table>
        )}
        <p className="sub">"Sent" means the mail server accepted the message. "Link opened" is recorded when the invitation link is opened in the app.</p>
      </Card>
    </div>
  );
}

function Directory() {
  const [d] = usePoll<any>("/hr/overview", 15000);
  if (!d) return <div className="loading">Loading…</div>;
  return (
    <div className="stack">
      <div className="page-h"><h1>All employees</h1><p>{d.existing} existing employees and {d.new_hires} new hires.</p></div>
      <Card>
        <table className="tbl"><thead><tr><th>Name</th><th>Title</th><th>Department</th><th>Status</th></tr></thead>
          <tbody>
            {d.hires.map((h: any) => <tr key={"n" + h.id} onClick={() => (location.hash = `/hr/employee/${h.id}`)}><td><b>{h.name}</b><div className="sub">{h.code}</div></td><td>{h.title}</td><td>{h.department}</td><td><Pill tone="info">New hire</Pill></td></tr>)}
            {d.existing_employees.map((e: any) => <tr key={e.id} className="noclick"><td><b>{e.name}</b><div className="sub">{e.code}</div></td><td>{e.title}</td><td>{e.department}</td><td><Pill tone="neutral">Existing</Pill></td></tr>)}
          </tbody></table>
      </Card>
    </div>
  );
}


const METRICS: [string, string, (s: any) => any, "high" | "low" | null][] = [
  ["skill_accuracy", "Skill assessment accuracy", (s) => `${s.skill_accuracy}%`, "high"],
  ["unsupported_claims", "Skills wrongly credited (unsupported)", (s) => s.unsupported_claims, "low"],
  ["mentors_on_right_team", "Mentors on the right team", (s) => `${s.mentors_on_right_team}%`, "high"],
  ["gaps_with_course", "Skill gaps covered by a course", (s) => `${s.gaps_with_course}%`, "high"],
  ["warnings_detected", "Problems flagged to HR (missing / wrong CV)", (s) => s.warnings_detected, null],
  ["injection_resisted", "Hidden-instruction attack resisted", (s) => (s.injection_resisted ? "Yes" : "No"), null],
  ["web_courses", "Courses found on the web (verified)", (s) => s.web_courses, null],
  ["guardrail_catches", "Safety-check catches", (s) => s.guardrail_catches, null],
  ["avg_seconds", "Average time per hire", (s) => `${s.avg_seconds}s`, null],
  ["avg_cost_usd", "Average cost per hire", (s) => (s.avg_cost_usd != null ? `$${s.avg_cost_usd}` : "$0"), null],
];
const SETUP_NAME: Record<string, string> = { sonnet: "Claude Sonnet 5.5 (used)", haiku: "Claude Haiku 5.5", rules: "Rules only (baseline)" };
const KIND: Record<string, string> = { missing_cv: "No CV uploaded", wrong_person_cv: "CV belongs to someone else", prompt_injection: "CV with hidden instructions to the AI", minimal_cv: "Very short CV" };

function Evaluation() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api("/hr/evaluation").then(setD).catch(() => setD({ setups: [] })); }, []);
  if (!d) return <div className="loading">Loading…</div>;
  const setups = d.setups;
  const best = (key: string, dir: "high" | "low" | null) => {
    if (!dir) return null;
    const vals = setups.map((x: any) => Number(x.summary[key]));
    return dir === "high" ? Math.max(...vals) : Math.min(...vals);
  };
  const sonnet = setups.find((x: any) => x.summary.setup === "sonnet");
  const rules = setups.find((x: any) => x.summary.setup === "rules");
  const t = d.tests;
  return (
    <div className="stack narrow-page">
      <div className="page-h"><h1>Evaluation</h1><p>Every number below comes from real, re-runnable tests — not typed in by hand.</p></div>

      <Card title="1 · Unseen test hires: Claude vs. a simpler baseline" action={setups[0] && <span className="sub">{setups[0].summary.cases} hires not used during development · run {setups[0].ran_at}</span>}>
        {setups.length === 0 ? <Empty>No evaluation results yet.</Empty> : (
          <div className="ws-wrap"><table className="tbl evtbl">
            <thead><tr><th>Measure</th>{setups.map((x: any) => <th key={x.summary.setup}>{SETUP_NAME[x.summary.setup]}</th>)}</tr></thead>
            <tbody>{METRICS.map(([k, label, fmt, dir]) => {
              const b = best(k, dir);
              return <tr key={k} className="noclick"><td>{label}</td>{setups.map((x: any) => (
                <td key={x.summary.setup} className={b !== null && Number(x.summary[k]) === b ? "best" : ""}>{fmt(x.summary)}</td>))}</tr>;
            })}</tbody>
          </table></div>
        )}
        <p className="sub">12 fictional hires across 8 roles, each with an answer sheet of which skills the CV truly proves. “Unsupported” = a skill credited without real evidence.
          “Safety-check catches” counts plan items the validator had to reject or correct on this set; the checks themselves are proven with deliberately wrong inputs (invented quotes, courses, links, mentors) in the automated tests below.</p>
      </Card>

      {sonnet && <Card title="2 · Robustness & adaptation (Claude Sonnet 5.5)">
        {sonnet.cases.filter((c: any) => c.kind !== "normal").map((c: any) => {
          const rb = rules?.cases.find((r: any) => r.id === c.id);
          const ok = c.unsupported_claims.length === 0 && (!c.warning_expected || c.warning_found);
          return <div key={c.id} className="li row between"><div><b>{KIND[c.kind] || c.kind}</b>
            <div className="sub">{c.warning_expected ? (c.warning_found ? "Flagged to HR ✓ · " : "Not flagged · ") : ""}{c.unsupported_claims.length ? `wrongly credited: ${c.unsupported_claims.join(", ")}` : "no skills wrongly credited"}
              {rb ? ` · rules baseline: ${rb.unsupported_claims.length} wrongly credited${rb.warning_expected ? (rb.warning_found ? ", flagged" : ", not flagged") : ""}` : ""}</div></div>
            <Pill tone={ok ? "ok" : "bad"}>{ok ? "Pass" : "Fail"}</Pill></div>;
        })}
        {sonnet.adaptation && <div className="li row between"><div><b>Project changed (Al Noor → Metro Depot) — agent re-plans</b>
          <div className="sub">{sonnet.adaptation.mentors_on_new_project_or_manager}/{sonnet.adaptation.mentors} mentors moved to the new project team or manager</div></div>
          <Pill tone={sonnet.adaptation.mentors_on_new_project_or_manager === sonnet.adaptation.mentors ? "ok" : "warn"}>{sonnet.adaptation.mentors_on_new_project_or_manager === sonnet.adaptation.mentors ? "Pass" : "Partial"}</Pill></div>}
        {sonnet.fallback && <div className="li row between"><div><b>Claude unavailable — service keeps working</b>
          <div className="sub">Plan produced by: {sonnet.fallback.source} · valid plan: {sonnet.fallback.valid_plan ? "yes" : "no"}</div></div>
          <Pill tone={sonnet.fallback.valid_plan && String(sonnet.fallback.source).startsWith("Rules") ? "ok" : "bad"}>{sonnet.fallback.valid_plan ? "Pass" : "Fail"}</Pill></div>}
      </Card>}

      <Card title="3 · Automated tests" action={t && <Pill tone={t.failed ? "bad" : "ok"}>{t.passed}/{t.total} passed</Pill>}>
        {!t ? <Empty>Not run yet.</Empty> : <>
          <p className="sub" style={{ marginTop: 0 }}>Run {t.ran_at} · {t.seconds}s · re-run with <code>./scripts/test.sh</code> — also runs automatically on GitHub for every change. Claude is replaced by recorded responses so results are repeatable.</p>
          <div className="testlist">{t.tests.map((x: any) => <div key={x.name}><span className={x.ok ? "tok" : "tbad"}>{x.ok ? "✓" : "✗"}</span> {x.label}</div>)}</div>
        </>}
      </Card>

      <Card title="4 · What testing found — and what we changed">
        <table className="tbl"><thead><tr><th>Area</th><th>Found</th><th>Fix</th><th>Verified by</th></tr></thead>
          <tbody>{d.iterations.map((x: any, i: number) => <tr key={i} className="noclick"><td><b>{x.area}</b></td><td className="sub">{x.found}</td><td className="sub">{x.fix}</td><td className="sub">{x.check}</td></tr>)}</tbody></table>
      </Card>

      <Card title="5 · Key decisions & trade-offs">
        {d.decisions.map((x: any, i: number) => <div key={i} className="li"><b>{x.decision}</b><div className="sub">{x.why}</div><div className="sub"><i>Trade-off:</i> {x.tradeoff}</div></div>)}
      </Card>
    </div>
  );
}
