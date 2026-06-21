import type { Metadata } from "next";
import { Suspense } from "react";
import { redirect } from "next/navigation";
import { Warehouse } from "lucide-react";
import { LoginForm } from "@/components/auth/LoginForm";
import { getServerSessionUser } from "@/lib/auth/session";
import { safeNextPath } from "@/lib/auth/redirects";

export const metadata: Metadata = {
  title: "Sign In - TrackFlow Backoffice",
  description: "Sign in to the internal TrackFlow Back Office.",
};

type LoginPageProps = {
  searchParams?: Promise<{
    next?: string;
  }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = (await searchParams) ?? {};
  const nextPath = safeNextPath(params.next);
  const user = await getServerSessionUser();

  if (user?.must_change_password) {
    redirect(`/account/change-password?next=${encodeURIComponent(nextPath)}`);
  }

  if (user) {
    redirect(nextPath);
  }

  return (
    <main className="min-h-screen bg-neutral-50 px-4 py-10 sm:px-6">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-md flex-col justify-center">
        <div className="rounded-lg border border-neutral-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-navy text-white">
              <Warehouse className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">TrackFlow</p>
              <h1 className="text-2xl font-black text-navy-deep">Backoffice sign in</h1>
            </div>
          </div>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </div>
      </div>
    </main>
  );
}
