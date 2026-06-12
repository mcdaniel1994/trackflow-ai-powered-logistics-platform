"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, ClipboardList, Users, type LucideIcon } from "lucide-react";

interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const navigationItems: NavigationItem[] = [
  { label: "Inventory + Carriers", href: "/", icon: Boxes },
  { label: "Incidents", href: "/incidents", icon: ClipboardList },
  { label: "Talent Pipeline", href: "/talent", icon: Users },
];

function isActivePath(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function BackofficeNavigation() {
  const pathname = usePathname();

  return (
    <nav className="min-w-0" aria-label="Backoffice navigation">
      <ul className="flex max-w-full gap-2 overflow-x-auto lg:block lg:space-y-2">
        {navigationItems.map((item) => {
          const active = isActivePath(pathname, item.href);

          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-w-max items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition lg:w-full lg:min-w-0 ${
                  active
                    ? "border-navy bg-navy text-white shadow-sm"
                    : "border-transparent text-neutral-600 hover:border-mist hover:bg-ivory hover:text-navy"
                }`}
              >
                <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

