import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/transactions", label: "Transactions", icon: "⇄" },
  { to: "/review-queue", label: "Review Queue", icon: "⛁" },
  { to: "/pnl", label: "P&L", icon: "▤" },
  { to: "/variance", label: "Variance", icon: "⇅" },
  { to: "/analyst", label: "AI Analyst", icon: "✦" },
  { to: "/how-it-works", label: "How It Works", icon: "⑃" },
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <aside className="fixed inset-y-0 left-0 w-60 bg-slate-900 text-slate-300 flex flex-col">
        <div className="px-5 py-6 border-b border-slate-800">
          <div className="text-lg font-semibold text-white tracking-tight">FINZ</div>
          <div className="text-xs text-slate-400 mt-0.5">AI-Native Financial Review</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-white/10 text-white font-medium"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`
              }
            >
              <span className="w-4 text-center">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-slate-800 text-[11px] text-slate-500">
          NYC Restaurant Co.
          <br />
          Jan – Mar 2026 dataset
        </div>
      </aside>
      <main className="ml-60 px-8 py-6">
        <Outlet />
      </main>
    </div>
  );
}