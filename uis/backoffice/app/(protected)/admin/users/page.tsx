import type { Metadata } from "next";
import { AdminUsersView } from "@/components/admin/AdminUsersView";

export const metadata: Metadata = {
  title: "User Management - TrackFlow Backoffice",
  description: "Admin-only Back Office user management.",
};

export default function AdminUsersPage() {
  return <AdminUsersView />;
}
