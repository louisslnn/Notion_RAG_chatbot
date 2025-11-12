import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "./AuthProvider";

const navItems = [
  { to: "/chat", label: "Chat" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/upload", label: "Upload Docs" },
];

function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-surface text-foreground">
      <aside className="hidden w-64 flex-col border-r border-border bg-panel/80 p-6 backdrop-blur md:flex">
        <div className="mb-10">
          <h1 className="text-lg font-semibold tracking-wide text-accent">Notion RAG Workspace</h1>
          <p className="text-sm text-muted">Engineer-first retrieval augmented chat.</p>
        </div>
        <nav className="flex flex-1 flex-col gap-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "rounded-md px-3 py-2 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-accent text-white shadow-lg shadow-accent/30"
                    : "text-muted hover:bg-hover hover:text-foreground",
                ].join(" ")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-10 rounded-md bg-hover/60 p-4 text-sm text-muted">
          <p className="font-semibold text-foreground">{user?.email}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-2 inline-flex items-center rounded bg-accent/90 px-3 py-1 text-xs font-semibold text-white shadow transition hover:bg-accent"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border bg-panel px-4 shadow-sm md:hidden">
          <span className="text-sm font-semibold text-accent">Notion RAG Workspace</span>
          <button
            type="button"
            onClick={logout}
            className="rounded bg-accent px-3 py-1 text-sm font-medium text-white"
          >
            Sign out
          </button>
        </header>
        <section className="flex flex-1 flex-col overflow-hidden">
          <Outlet />
        </section>
      </main>
    </div>
  );
}

export default Layout;

