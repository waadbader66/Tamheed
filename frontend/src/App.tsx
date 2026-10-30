import { useEffect, useState } from "react";
import { api } from "./api";
import { Login, ChangePassword } from "./Login";
import { HrApp } from "./Hr";
import { EmployeeApp } from "./Employee";

export default function App() {
  const [user, setUser] = useState<any>(undefined);
  const [notice, setNotice] = useState("");
  const [toast, setToast] = useState("");
  useEffect(() => {
    // Opening the invitation link always starts from a clean sign-in page, even if someone (e.g. HR) is signed in.
    if (location.hash.includes("invite=")) { api("/auth/logout", { body: {} }).catch(() => {}).finally(() => setUser(null)); return; }
    api("/auth/me").then(setUser).catch(() => setUser(null));
  }, []);
  useEffect(() => {
    const expired = () => { setUser(null); setNotice("Your session has ended. Please sign in again."); location.hash = "/login"; };
    const failed = (e: any) => { setToast(e.detail || "Something went wrong"); setTimeout(() => setToast(""), 4000); };
    addEventListener("session-expired", expired); addEventListener("api-error", failed);
    return () => { removeEventListener("session-expired", expired); removeEventListener("api-error", failed); };
  }, []);
  const logout = async () => { await api("/auth/logout", { body: {} }).catch(() => {}); setUser(null); location.hash = "/login"; };
  if (user === undefined) return <div className="boot" />;
  if (!user) return <Login notice={notice} onDone={(u) => { setNotice(""); setUser(u); location.hash = u.kind === "hr" ? "/hr" : "/me"; }} />;
  if (user.must_change_password) return <ChangePassword user={user} onDone={(u) => { setUser(u); location.hash = "/me"; }} onLogout={logout} />;
  // The workspace is decided by the account's server-side role. There is no role switching.
  return <>
    {user.kind === "hr" ? <HrApp user={user} onLogout={logout} /> : <EmployeeApp user={user} onLogout={logout} />}
    {toast && <div className="toast" role="alert">{toast}</div>}
  </>;
}
