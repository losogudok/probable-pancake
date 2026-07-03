import { BarChart3, BookOpenText, CircleHelp, GitFork, LogOut, Menu, Search, ShieldCheck, Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";
import { isMockMode } from "../api/api-provider";
import { roleLabels } from "../domain/labels";
import type { DemoRole } from "../domain/types";
import { useSession } from "./session-context";
import s from "../styles/ui.module.css";

const nav = [
  { to: "/", label: "Поиск", icon: Search, end: true }, { to: "/graph", label: "Граф", icon: GitFork },
  { to: "/sources", label: "Источники", icon: BookOpenText }, { to: "/quality", label: "Качество", icon: ShieldCheck },
  { to: "/analytics", label: "Аналитика", icon: BarChart3 },
];
const roles = Object.keys(roleLabels) as DemoRole[];

export function App() {
  const [profileOpen, setProfileOpen] = useState(false); const { role, setRole, resetDemo } = useSession();
  return <div className={s.appShell}>
    <aside className={s.sidebar}>
      <div className={s.brand}><span className={s.brandMark}><Sparkles size={20} /></span><span><b>Научный клубок</b><small>R&D knowledge map</small></span></div>
      <nav className={s.desktopNav} aria-label="Основная навигация">{nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `${s.navItem} ${isActive ? s.navActive : ""}`}><Icon size={19}/><span>{label}</span></NavLink>)}</nav>
      <div className={s.sidebarFooter}><div className={s.statusLine}><span className={s.statusDot}/><span>{isMockMode ? "Демо-данные" : "API подключён"}</span></div><button className={s.helpButton}><CircleHelp size={18}/>Как пользоваться</button></div>
    </aside>
    <div className={s.workspace}>
      <header className={s.topbar}>
        <div className={s.mobileBrand}><span className={s.brandMark}><Sparkles size={18}/></span><b>Научный клубок</b></div>
        <div className={s.topbarSpacer}/>
        {isMockMode && <span className={s.demoBadge}>ДЕМО-РЕЖИМ</span>}
        <div className={s.profileWrap}>
          <button className={s.profileButton} onClick={() => setProfileOpen((v) => !v)} aria-expanded={profileOpen}><span className={s.avatar}>НИ</span><span className={s.profileText}><b>{roleLabels[role]}</b><small>Демонстрационная роль</small></span><Menu size={17}/></button>
          {profileOpen && <div className={s.profileMenu} role="menu"><p>Роль в демо-режиме</p>{roles.map((item) => <button key={item} className={item === role ? s.menuSelected : ""} onClick={() => { setRole(item); setProfileOpen(false); }}>{roleLabels[item]}{item === role && <span>✓</span>}</button>)}<hr/><button onClick={resetDemo}><LogOut size={16}/>Сбросить демо-данные</button></div>}
        </div>
      </header>
      <main className={s.main}><Outlet/></main>
    </div>
    <nav className={s.mobileNav} aria-label="Мобильная навигация">{nav.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `${s.mobileNavItem} ${isActive ? s.mobileNavActive : ""}`}><Icon size={20}/><span>{label}</span></NavLink>)}</nav>
  </div>;
}
