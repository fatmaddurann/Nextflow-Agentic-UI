import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Play, List, Container, BookOpen,
  Dna, Menu, X, Activity, ChevronRight
} from 'lucide-react'

import Dashboard from './components/Dashboard'
import WorkflowRunner from './components/WorkflowRunner'
import WorkflowList from './components/WorkflowList'
import WorkflowDetail from './components/WorkflowDetail'
import ContainerPanel from './components/ContainerPanel'
import KnowledgePanel from './components/KnowledgePanel'

const NAV_ITEMS = [
  { path: '/',            label: 'Dashboard',  icon: LayoutDashboard },
  { path: '/run',         label: 'Run Pipeline', icon: Play },
  { path: '/workflows',   label: 'Workflows',  icon: List },
  { path: '/containers',  label: 'Containers', icon: Container },
  { path: '/knowledge',   label: 'Knowledge',  icon: BookOpen },
]

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-slate-900">

        {/* ── Sidebar ───────────────────────────────────────────────────── */}
        <aside className={`
          ${sidebarOpen ? 'w-56' : 'w-14'} transition-all duration-300
          flex flex-col bg-slate-950 border-r border-slate-800 flex-shrink-0
        `}>
          {/* Logo */}
          <div className="flex items-center gap-3 px-3 py-4 border-b border-slate-800">
            <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600
                            rounded-lg flex items-center justify-center">
              <Dna className="w-5 h-5 text-white" />
            </div>
            {sidebarOpen && (
              <div className="overflow-hidden">
                <div className="text-sm font-bold text-white whitespace-nowrap">NF-Agentic</div>
                <div className="text-xs text-slate-500 whitespace-nowrap">Pipeline Manager</div>
              </div>
            )}
          </div>

          {/* Nav links */}
          <nav className="flex-1 py-4 space-y-1 px-2">
            {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                end={path === '/'}
                className={({ isActive }) => `
                  flex items-center gap-3 px-2 py-2 rounded-lg transition-colors
                  ${isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-700/50'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}
                `}
                title={!sidebarOpen ? label : undefined}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {sidebarOpen && <span className="text-sm font-medium">{label}</span>}
              </NavLink>
            ))}
          </nav>

          {/* Status indicator */}
          {sidebarOpen && (
            <div className="px-3 py-3 border-t border-slate-800">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Activity className="w-3 h-3 text-green-400" />
                <span>System Online</span>
              </div>
            </div>
          )}

          {/* Toggle button */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-3 text-slate-500 hover:text-slate-300 hover:bg-slate-800
                       border-t border-slate-800 transition-colors"
          >
            {sidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </aside>

        {/* ── Main Content ──────────────────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto">
          {/* Top bar */}
          <div className="sticky top-0 z-10 bg-slate-900/80 backdrop-blur border-b
                          border-slate-800 px-6 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ChevronRight className="w-3 h-3" />
              <span>Nextflow-Agentic-UI</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-400 relative">
                <div className="absolute inset-0 rounded-full bg-green-400 animate-ping opacity-75" />
              </div>
              <span className="text-xs text-slate-400">API Connected</span>
            </div>
          </div>

          {/* Page content */}
          <div className="p-6">
            <Routes>
              <Route path="/"               element={<Dashboard />} />
              <Route path="/run"            element={<WorkflowRunner />} />
              <Route path="/workflows"      element={<WorkflowList />} />
              <Route path="/workflows/:id"  element={<WorkflowDetail />} />
              <Route path="/containers"     element={<ContainerPanel />} />
              <Route path="/knowledge"      element={<KnowledgePanel />} />
            </Routes>
          </div>
        </main>

      </div>
    </BrowserRouter>
  )
}
