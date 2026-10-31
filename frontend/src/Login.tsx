import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import { Logo, PRODUCT, COMPANY, TAGLINE } from "./brand";

const WORDS = ["ready on day one.", "personally guided.", "never left guessing.", "welcomed by name."];
const STEPS = [["1", "HR adds a new hire"], ["2", "AI agent reads the CV"], ["3", "Plan, mentors & courses"], ["4", "Ready on day one"]];

function LoginArt() {
  const [w, setW] = useState(0);
  useEffect(() => { const t = setInterval(() => setW((x) => (x + 1) % WORDS.length), 2600); return () => clearInterval(t); }, []);
  return (
    <div className="login-art" aria-hidden>
      <div className="intro">
        <div className="intro-eyebrow">AI onboarding · {COMPANY}</div>
        <h2 className="intro-h">Every new hire,<br /><span key={w} className="intro-word">{WORDS[w]}</span></h2>
      </div>
      <div className="steps">
        {STEPS.map(([n, label], i) => <i key={n} style={{ ["--d" as any]: `${i * 0.9}s` }}><em><b>{n}</b>{label}</em></i>)}
      </div>
    </div>
  );
}

export function Login({ onDone, notice }: { onDone: (u: any) => void; notice?: string }) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const invited = params.has("invite");
  const [username, setU] = useState(params.get("u") || "");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [judgeOn, setJudgeOn] = useState(false);
  useEffect(() => { const t = params.get("invite"); if (t) api("/invitations/viewed", { body: { token: t } }).catch(() => {}); }, []);
  useEffect(() => { if (!invited) api("/health").then((h) => setJudgeOn(!!h.judge_access)).catch(() => {}); }, []);
  async function judge() {
    setBusy(true); setErr("");
    try { onDone(await api("/auth/judge", { body: {} })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (judgeOn && !username.trim() && !password) return judge();
    if (!username.trim() || !password) { setErr("Enter your username and password."); return; }
    setBusy(true); setErr("");
    try { onDone(await api("/auth/login", { body: { username: username.trim(), password: password.trim() } })); }
    catch (e: any) { setErr(e.message || "Sign-in failed"); }
    finally { setBusy(false); }
  }
  return (
    <div className="login">
      <LoginArt />
      <form className="login-card" onSubmit={submit} noValidate>
        <Logo size={56} />
        <h1>{PRODUCT}</h1>
        <div className="company">{COMPANY}</div>
        <p className="tagline">{TAGLINE}</p>
        {invited && <div className="note">Welcome! Enter the temporary password from your invitation email. You'll choose your own password next.</div>}
        <label>Username<input autoComplete="username" value={username} onChange={(e) => setU(e.target.value)} placeholder="name@company.com" /></label>
        <label>{invited ? "Temporary password" : "Password"}<input type="password" autoComplete={invited ? "off" : "current-password"} autoFocus={invited} value={password} onChange={(e) => setP(e.target.value)} /></label>
        {notice && !err && <div className="note">{notice}</div>}
        {err && <div className="err" role="alert">{err}</div>}
        <button className="primary big" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {judgeOn && <div className="judge-note"><b>Hackathon judges:</b> leave username and password empty and click <b>Sign in</b>.</div>}
      </form>
    </div>
  );
}

export function ChangePassword({ user, onDone, onLogout }: { user: any; onDone: (u: any) => void; onLogout: () => void }) {
  const [cur, setCur] = useState(""); const [n1, setN1] = useState(""); const [n2, setN2] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr("");
    if (n1.length < 10) return setErr("Use at least 10 characters.");
    if (n1 !== n2) return setErr("The new passwords don't match.");
    setBusy(true);
    try { onDone(await api("/auth/change-password", { body: { current: cur, new: n1 } })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="login">
      <LoginArt />
      <form className="login-card" onSubmit={submit}>
        <Logo size={48} />
        <h1 style={{ fontSize: 26 }}>Welcome, {user.name.split(" ")[0]}</h1>
        <p className="tagline">Choose your own password to open your onboarding space.</p>
        <label>Temporary password (from your email)<input type="password" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
        <label>New password<input type="password" value={n1} onChange={(e) => setN1(e.target.value)} autoComplete="new-password" /></label>
        <label>Confirm new password<input type="password" value={n2} onChange={(e) => setN2(e.target.value)} autoComplete="new-password" /></label>
        {err && <div className="err" role="alert">{err}</div>}
        <button className="primary big" disabled={busy}>{busy ? "Saving…" : "Set password & continue"}</button>
        <button type="button" className="link" onClick={onLogout}>Sign out</button>
      </form>
    </div>
  );
}
