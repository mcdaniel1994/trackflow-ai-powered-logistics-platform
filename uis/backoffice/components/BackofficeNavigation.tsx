"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Boxes,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Package,
  ShieldCheck,
  UserCircle,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/lib/auth/context";

interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  activePrefix?: string;
}

const navigationItems: NavigationItem[] = [
  { label: "Operations Overview", href: "/", icon: LayoutDashboard },
  {
    label: "Inventory Management",
    href: "/backoffice/inventory/products",
    icon: Package,
    activePrefix: "/backoffice/inventory",
  },
  {
    label: "Telemetry",
    href: "/backoffice/telemetry/fulfilment",
    icon: Activity,
    activePrefix: "/backoffice/telemetry",
  },
  {
    label: "Business Reporting",
    href: "/backoffice/reporting",
    icon: BarChart3,
    activePrefix: "/backoffice/reporting",
  },
  {
    label: "Carrier Scoring",
    href: "/backoffice/carrier-scoring",
    icon: Boxes,
    activePrefix: "/backoffice/carrier-scoring",
  },
  { label: "Incidents", href: "/incidents", icon: ClipboardList },
  { label: "Suppliers", href: "/suppliers", icon: Package },
  { label: "Talent Pipeline", href: "/talent", icon: Users },
  { label: "Account", href: "/account/profile", icon: UserCircle },
];

function isActivePath(pathname: string, item: NavigationItem) {
  if (item.href === "/") {
    return pathname === "/";
  }
  if (item.activePrefix) {
    return pathname === item.activePrefix || pathname.startsWith(`${item.activePrefix}/`);
  }
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

type BackofficeNavigationProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

export function BackofficeNavigation({ collapsed = false, onNavigate }: BackofficeNavigationProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const items =
    user.role === "admin"
      ? [...navigationItems, { label: "User Management", href: "/admin/users", icon: ShieldCheck }]
      : navigationItems;

  return (
    <nav className="min-w-0" aria-label="Backoffice navigation">
      <ul className="max-w-full space-y-2">
        {items.map((item) => {
          const active = isActivePath(pathname, item);

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                onClick={onNavigate}
                className={`flex w-full min-w-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition ${
                  collapsed ? "lg:justify-center lg:px-2" : ""
                } ${
                  active
                    ? "border-navy bg-navy text-white shadow-sm"
                    : "border-transparent text-neutral-600 hover:border-mist hover:bg-ivory hover:text-navy"
                }`}
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className={`truncate ${collapsed ? "lg:sr-only" : ""}`}>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 border-t border-mist pt-4">
        <div className={`mb-3 min-w-0 ${collapsed ? "lg:text-center" : ""}`}>
          <p className={`truncate text-xs font-bold uppercase text-neutral-500 ${collapsed ? "lg:sr-only" : ""}`}>
            Signed in
          </p>
          <p className={`truncate text-sm font-black text-navy-deep ${collapsed ? "lg:sr-only" : ""}`}>
            {user.name}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            onNavigate?.();
            void logout();
          }}
          title={collapsed ? "Log out" : undefined}
          className={`flex w-full min-w-0 items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-sm font-bold text-neutral-600 transition hover:border-mist hover:bg-ivory hover:text-navy ${
            collapsed ? "lg:justify-center lg:px-2" : ""
          }`}
        >
          <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className={`truncate ${collapsed ? "lg:sr-only" : ""}`}>Log out</span>
        </button>
      </div>
    </nav>
  );
}
