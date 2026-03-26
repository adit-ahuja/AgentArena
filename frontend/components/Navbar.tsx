import Link from "next/link";
import { useRouter } from "next/router";
import { clsx } from "clsx";

const NAV = [
  { href: "/",          label: "Leaderboard" },
  { href: "/submit",    label: "Submit Agent" },
  { href: "/tasks",     label: "Task Bank"    },
  { href: "/compare",   label: "Compare"      },
  { href: "/docs",      label: "Docs"         },
];

export default function Navbar() {
  const { pathname } = useRouter();

  return (
    <nav
      style={{
        background: "rgba(18,18,26,0.95)",
        borderBottom: "1px solid var(--border)",
        backdropFilter: "blur(12px)",
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 no-underline">
          <span
            style={{
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              borderRadius: "8px",
              width: 30,
              height: 30,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              fontWeight: 700,
              color: "#fff",
            }}
          >
            ⚔
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "var(--text)",
              letterSpacing: "-0.02em",
            }}
          >
            Agent<span style={{ color: "var(--accent)" }}>Arena</span>
          </span>
          <span
            style={{
              fontSize: 10,
              color: "var(--subtle)",
              background: "var(--muted)",
              borderRadius: 4,
              padding: "1px 6px",
              fontFamily: "monospace",
            }}
          >
            v1.0
          </span>
        </Link>

        {/* Nav Links */}
        <div className="flex items-center gap-1">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              style={{
                padding: "4px 12px",
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                color: pathname === href ? "var(--text)" : "var(--subtle)",
                background: pathname === href ? "var(--muted)" : "transparent",
                textDecoration: "none",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => {
                if (pathname !== href)
                  (e.currentTarget as HTMLElement).style.color = "var(--text)";
              }}
              onMouseLeave={e => {
                if (pathname !== href)
                  (e.currentTarget as HTMLElement).style.color = "var(--subtle)";
              }}
            >
              {label}
            </Link>
          ))}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--green)" }}>
            <span className="live-dot" />
            Live
          </span>
          <Link
            href="/submit"
            style={{
              background: "linear-gradient(135deg, #7c3aed, #6d28d9)",
              color: "#fff",
              padding: "6px 14px",
              borderRadius: 7,
              fontSize: 13,
              fontWeight: 600,
              textDecoration: "none",
              transition: "opacity 0.15s",
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = "0.85"; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = "1"; }}
          >
            Run Benchmark
          </Link>
        </div>
      </div>
    </nav>
  );
}
