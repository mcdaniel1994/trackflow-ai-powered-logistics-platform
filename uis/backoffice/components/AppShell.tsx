import type { ReactNode } from "react";
import { Activity, Boxes, ShieldCheck, Truck, Warehouse, type LucideIcon } from "lucide-react";

interface NavigationItem {
  label: string;
  href: string;
  active: boolean;
  icon: LucideIcon;
}

const navigationItems: NavigationItem[] = [
  { label: "Inventory + Carriers", href: "/", active: true, icon: Boxes },
  { label: "Orders", href: "/", active: false, icon: Truck },
  { label: "Returns", href: "/", active: false, icon: Activity },
  { label: "Client Health", href: "/", active: false, icon: ShieldCheck },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-20 border-b border-mist/90 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-[100vw] items-center justify-between px-4 sm:px-6 lg:max-w-7xl lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy text-white shadow-sm">
              <Warehouse className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">
                TrackFlow
              </p>
              <p className="truncate text-lg font-black text-navy-deep">Backoffice</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 rounded-lg border border-mist bg-ivory px-3 py-2 text-sm font-bold text-navy sm:flex">
            <Activity className="h-4 w-4 text-teal" aria-hidden="true" />
            Internal operations
          </div>
        </div>
      </header>
      <div className="mx-auto grid w-full max-w-[100vw] grid-cols-1 overflow-hidden lg:max-w-7xl lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-w-0 w-full max-w-[100vw] overflow-hidden border-b border-mist/90 bg-white px-4 py-4 lg:min-h-[calc(100vh-4rem)] lg:border-b-0 lg:border-r lg:px-6">
          <nav className="min-w-0" aria-label="Backoffice navigation">
            <ul className="flex max-w-full gap-2 overflow-x-auto lg:block lg:space-y-2">
              {navigationItems.map((item) => (
                <li key={item.label}>
                  <a
                    href={item.href}
                    aria-current={item.active ? "page" : undefined}
                    className={`flex min-w-max items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition lg:min-w-0 lg:w-full ${
                      item.active
                        ? "border-navy bg-navy text-white shadow-sm"
                        : "border-transparent text-neutral-600 hover:border-mist hover:bg-ivory hover:text-navy"
                    }`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{item.label}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
        <main className="min-w-0 w-full max-w-[100vw] overflow-hidden px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
