import {
  Activity,
  BarChart3,
  Blocks,
  Files,
  LayoutDashboard,
  Route,
  Search,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useHealth } from '../lib/queries'

const navItems = [
  { to: '/', label: '系统总览', short: 'Overview', icon: LayoutDashboard, index: '01' },
  { to: '/documents', label: '文档管理', short: 'Documents', icon: Files, index: '02' },
  { to: '/chunk-lab', label: 'Chunk Lab', short: 'Chunk Lab', icon: Blocks, index: '03' },
  { to: '/retrieval', label: '检索对比', short: 'Retrieval', icon: Search, index: '04' },
  { to: '/evaluation', label: '评测看板', short: 'Evaluation', icon: BarChart3, index: '05' },
  { to: '/trace', label: 'Trace 详情', short: 'Trace', icon: Route, index: '06' },
]

const titles: Record<string, string> = {
  '/': 'System overview',
  '/documents': 'Document registry',
  '/chunk-lab': 'Chunk laboratory',
  '/retrieval': 'Strategy comparison',
  '/evaluation': 'Evaluation ledger',
  '/trace': 'Trace inspector',
}

export function AppShell() {
  const location = useLocation()
  const health = useHealth()
  const pageTitle =
    titles[location.pathname] ??
    (location.pathname.startsWith('/trace/') ? 'Trace inspector' : 'Research workbench')

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/">
          <span className="brand-mark">P/R</span>
          <span className="brand-copy">
            <strong>PolicyRAG</strong>
            <small>Research Studio</small>
          </span>
        </NavLink>

        <div className="sidebar-rule" />

        <nav className="nav-list" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`}
                end={item.to === '/'}
                key={item.to}
                to={item.to}
              >
                <span className="nav-index">{item.index}</span>
                <Icon aria-hidden="true" size={17} strokeWidth={1.7} />
                <span className="nav-copy">
                  <span>{item.label}</span>
                  <small>{item.short}</small>
                </span>
              </NavLink>
            )
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="sidebar-footline">
            <Activity size={14} />
            <span>DEMO / LOCAL</span>
          </div>
          <p>Public policy fixtures · No company data</p>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">POLICY INTELLIGENCE / RETRIEVAL OPERATIONS</span>
            <h1>{pageTitle}</h1>
          </div>
          <div className="topbar-actions">
            <div className={`live-state ${health.data?.status === 'ok' ? 'is-live' : ''}`}>
              <span className="live-dot" />
              <span>{health.data?.status === 'ok' ? 'API ONLINE' : 'API OFFLINE'}</span>
            </div>
            <span className="version-chip">v0.2.0 / release</span>
          </div>
        </header>
        <main className="page-stage">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
