import { useLocation, NavLink } from 'react-router-dom'
import DemoPage from './pages/DemoPage'
import ReviewsPage from './pages/ReviewsPage'
import SessionsPage from './pages/SessionsPage'

export default function App() {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="border-b border-gray-800 bg-gray-900 px-6 py-3 flex items-center gap-6">
        <span className="text-cyan-400 font-bold text-lg tracking-wide">AuditBot</span>
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `text-sm px-3 py-1 rounded transition-colors ${isActive ? 'bg-cyan-900 text-cyan-300' : 'text-gray-400 hover:text-gray-200'}`
          }
        >
          Demo
        </NavLink>
        <NavLink
          to="/reviews"
          className={({ isActive }) =>
            `text-sm px-3 py-1 rounded transition-colors ${isActive ? 'bg-yellow-900 text-yellow-300' : 'text-gray-400 hover:text-gray-200'}`
          }
        >
          HITL Reviews
        </NavLink>
        <NavLink
          to="/sessions"
          className={({ isActive }) =>
            `text-sm px-3 py-1 rounded transition-colors ${isActive ? 'bg-purple-900 text-purple-300' : 'text-gray-400 hover:text-gray-200'}`
          }
        >
          Sessions
        </NavLink>
      </nav>

      {/* Pages — DemoPage always stays mounted to preserve state */}
      <main className="flex-1 overflow-hidden">
        {/* DemoPage: always mounted, hidden when on other routes */}
        <div className={pathname === '/' ? 'h-full' : 'hidden'}>
          <DemoPage />
        </div>

        {pathname === '/reviews'  && <ReviewsPage />}
        {pathname === '/sessions' && <SessionsPage />}
      </main>
    </div>
  )
}
