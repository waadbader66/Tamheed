import { ReactNode } from "react";
import { Wordmark, COMPANY } from "./brand";

export type NavItem = { key: string; label: string; icon: string; badge?: number | string };

export function Shell({ nav, active, onNav, user, onLogout, children, scope }: {
  nav: NavItem[]; active: string; onNav: (k: string) => void; user: any; onLogout: () => void; children: ReactNode; scope: string;
}) {
  return (
    <div className="shell">
      <aside className="side">
        <Wordmark size={30} />
        <div className="scope">{scope}</div>
        <nav>
          {nav.map((n) => (
            <button key={n.key} className={"navbtn" + (active === n.key ? " on" : "")} onClick={() => onNav(n.key)}>
              <span className="ico">{n.icon}</span>{n.label}{n.badge ? <span className="nbadge">{n.badge}</span> : null}
            </button>
          ))}
        </nav>
        <div className="side-foot">{COMPANY}</div>
      </aside>
      <div className="main">
        <header className="top">
          <div className="crumb">{nav.find((n) => n.key === active)?.label}</div>
          <div className="who">
            <div className="avatar">{(user.name || "?").split(" ").map((s: string) => s[0]).slice(0, 2).join("")}</div>
            <div><div className="who-n">{user.name}</div><div className="who-t">{user.title}</div></div>
            <button className="ghost" onClick={onLogout}>Sign out</button>
          </div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

export const Card = ({ children, className = "", title, action }: { children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode }) => (
  <section className={"card " + className}>
    {(title || action) && <div className="card-h"><h3>{title}</h3>{action}</div>}
    {children}
  </section>
);

export const Pill = ({ tone = "neutral", children }: { tone?: string; children: ReactNode }) => <span className={"pill " + tone}>{children}</span>;

export const Bar = ({ value, tone = "brand" }: { value: number; tone?: string }) => (
  <div className="bar"><div className={"bar-f " + tone} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
);

export function Ring({ value, size = 120, label }: { value: number; size?: number; label?: string }) {
  const r = size / 2 - 10, c = 2 * Math.PI * r;
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--line)" strokeWidth="10" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--brand)" strokeWidth="10" fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset .6s" }} />
      </svg>
      <div className="ring-l"><b>{value}%</b>{label && <span>{label}</span>}</div>
    </div>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => <div className="empty">{children}</div>;

export function Md({ text }: { text: string }) {
  // tiny safe markdown: **bold**, [E1] refs, bullets, paragraphs
  const html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/^#+\s*(.+)$/gm, "<b>$1</b>")
    .replace(/\[([EDPJ]\d+)\]/g, '<span class="ref">$1</span>')
    .split(/\n{2,}/).map((p) => {
      // paragraphs may mix a lead-in line with bullet items
      let out = "", list: string[] = [], text: string[] = [];
      const flushText = () => { if (text.length) { out += "<p>" + text.join("<br/>") + "</p>"; text = []; } };
      const flushList = () => { if (list.length) { out += "<ul>" + list.map((l) => "<li>" + l + "</li>").join("") + "</ul>"; list = []; } };
      for (const l of p.split("\n")) {
        const m = l.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
        if (m) { flushText(); list.push(m[1]); } else { flushList(); text.push(l); }
      }
      flushText(); flushList();
      return out;
    }).join("");
  return <div className="md" dangerouslySetInnerHTML={{ __html: html }} />;
}
