import {
  Activity,
  BarChart3,
  Bot,
  Boxes,
  ClipboardList,
  FileText,
  LayoutDashboard,
  Package,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/lib/auth/types";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
  activePrefix?: string;
  badge?: string;
  disabled?: boolean;
}

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
  adminOnly?: boolean;
}

/**
 * Category-based navigation modelled on the Hostinger / Agent-OS reference. Groups are always
 * visible (nothing becomes unreachable); the top-center toggle instead switches the home
 * overview. Account and sign-out moved to the header account menu.
 */
export const navigationGroups: NavigationGroup[] = [
  {
    label: "Knowledge Base",
    items: [{ label: "Overview", href: "/", icon: LayoutDashboard }],
  },
  {
    label: "Business",
    items: [
      { label: "Business Reporting", href: "/backoffice/reporting", icon: BarChart3, activePrefix: "/backoffice/reporting" },
      { label: "Carrier Scoring", href: "/backoffice/carrier-scoring", icon: Boxes, activePrefix: "/backoffice/carrier-scoring" },
      { label: "Incidents", href: "/incidents", icon: ClipboardList },
      { label: "Suppliers", href: "/suppliers", icon: Package },
      { label: "Talent Pipeline", href: "/talent", icon: Users },
    ],
  },
  {
    label: "Technical Data",
    items: [
      {
        label: "Inventory Management",
        href: "/backoffice/inventory/products",
        icon: Package,
        activePrefix: "/backoffice/inventory",
      },
      {
        label: "Technical Telemetry",
        href: "/backoffice/telemetry/fulfilment",
        icon: Activity,
        activePrefix: "/backoffice/telemetry",
      },
    ],
  },
  {
    label: "Agent OS",
    items: [
      { label: "Agent OS", href: "/agent-os", icon: Bot, badge: "Soon" },
      { label: "RFP Desk", href: "/agent-os/rfp", icon: FileText, activePrefix: "/agent-os/rfp" },
    ],
  },
  {
    label: "Administration",
    adminOnly: true,
    items: [{ label: "User Management", href: "/admin/users", icon: ShieldCheck }],
  },
];

export function isActivePath(pathname: string, item: NavigationItem): boolean {
  if (item.href === "/") {
    return pathname === "/";
  }
  if (item.activePrefix) {
    return pathname === item.activePrefix || pathname.startsWith(`${item.activePrefix}/`);
  }
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function visibleGroups(role: UserRole): NavigationGroup[] {
  return navigationGroups.filter((group) => !group.adminOnly || role === "admin");
}
