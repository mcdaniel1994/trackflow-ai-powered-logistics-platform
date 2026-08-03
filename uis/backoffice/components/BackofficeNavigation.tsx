"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { type NavigationItem, isActivePath, visibleGroups } from "@/lib/backoffice/navigation";

type BackofficeNavigationProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

export function BackofficeNavigation({ collapsed = false, onNavigate }: BackofficeNavigationProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const groups = visibleGroups(user.role);

  return (
    <nav className="min-w-0 space-y-5" aria-label="Backoffice navigation">
      {groups.map((group) => (
        <div key={group.label} className="min-w-0">
          <p
            className={`mb-2 px-2 text-[0.65rem] font-black uppercase tracking-[0.14em] text-neutral-400 dark:text-neutral-500 ${
              collapsed ? "lg:sr-only" : ""
            }`}
          >
            {group.label}
          </p>
          <ul className="max-w-full space-y-1.5">
            {group.items.map((item) => (
              <li key={item.label}>
                <NavLink item={item} active={isActivePath(pathname, item)} collapsed={collapsed} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: NavigationItem;
  active: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const base = `flex w-full min-w-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-bold transition ${
    collapsed ? "lg:justify-center lg:px-2" : ""
  }`;

  const content = (
    <>
      <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className={`truncate ${collapsed ? "lg:sr-only" : ""}`}>{item.label}</span>
      {item.badge ? (
        <span className={`ml-auto rounded-full bg-teal/20 px-2 py-0.5 text-[0.6rem] font-black uppercase text-teal ${collapsed ? "lg:hidden" : ""}`}>
          {item.badge}
        </span>
      ) : null}
    </>
  );

  if (item.disabled) {
    return (
      <span
        aria-disabled="true"
        title={collapsed ? item.label : undefined}
        className={`${base} cursor-not-allowed border-transparent text-neutral-400 dark:text-neutral-600`}
      >
        {content}
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
      onClick={onNavigate}
      className={`${base} ${
        active
          ? "border-navy bg-navy text-white shadow-sm dark:border-sky dark:bg-sky"
          : "border-transparent text-neutral-600 hover:border-mist hover:bg-ivory hover:text-navy dark:text-neutral-300 dark:hover:border-ink-600 dark:hover:bg-ink-700 dark:hover:text-neutral-100"
      }`}
    >
      {content}
    </Link>
  );
}
