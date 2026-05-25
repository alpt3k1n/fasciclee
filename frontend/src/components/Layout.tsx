import { Outlet, Link, useLocation } from 'react-router-dom'

export default function Layout() {
  const loc = useLocation()

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/" className="font-semibold text-lg tracking-tight">
            Fasikül Üretici
          </Link>
          <nav className="flex gap-4 text-sm text-slate-600">
            <Link to="/" className={loc.pathname === '/' ? 'text-slate-900 font-medium' : 'hover:text-slate-900'}>
              Dersler
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
