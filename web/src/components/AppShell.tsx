import {
  Activity,
  BarChart3,
  Blocks,
  Files,
  LayoutDashboard,
  Route,
  Search,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

import { useHealth } from '../lib/queries'

const navItems = [
  { to: '/', label: '总览', icon: LayoutDashboard },
  { to: '/documents', label: '文档', icon: Files },
  { to: '/chunk-lab', label: '切片', icon: Blocks },
  { to: '/retrieval', label: '检索', icon: Search },
  { to: '/evaluation', label: '评测', icon: BarChart3 },
  { to: '/trace', label: 'Trace', icon: Route },
]


export function AppShell() {
  const health = useHealth()
  const online = health.data?.status === 'ok'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink aria-label="PolicyRAG" className="brand" to="/">
          <span className="brand-mark" aria-hidden="true">PR</span>
          <span className="brand-copy">
            <strong>PolicyRAG</strong>
            <small>检索评测</small>
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
                <Icon aria-hidden="true" size={17} strokeWidth={1.6} />
                <span className="nav-copy">{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="sidebar-status">
            <div className={`live-state ${online ? 'is-live' : ''}`}>
              <span className="live-dot" />
              <span>{online ? 'API 在线' : 'API 离线'}</span>
            </div>
            <span className="version-chip">v0.2</span>
          </div>
          <div className="sidebar-footline">
            <Activity size={12} />
            <span>本地公开数据</span>
          </div>
          <p>仅使用政策演示文件，不接入内部数据。</p>
        </div>
      </aside>

      <div className="workspace">
        <main className="page-stage">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
