import { redirect } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { RequirePasswordChangeGate } from "@/components/auth/RequirePasswordChangeGate";
import { AuthProvider } from "@/lib/auth/context";
import { getServerSessionUser } from "@/lib/auth/session";
import { loginPathFor, safeNextPath } from "@/lib/auth/redirects";
import { getRequestPath } from "@/lib/server/request-context";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const path = await getRequestPath();
  const user = await getServerSessionUser();

  if (!user) {
    redirect(loginPathFor(path));
  }

  if (user.must_change_password && !path.startsWith("/account/change-password")) {
    redirect(`/account/change-password?next=${encodeURIComponent(safeNextPath(path))}`);
  }

  if (path.startsWith("/admin") && user.role !== "admin") {
    redirect("/");
  }

  return (
    <AuthProvider initialUser={user}>
      <RequirePasswordChangeGate>
        <AppShell>{children}</AppShell>
      </RequirePasswordChangeGate>
    </AuthProvider>
  );
}
