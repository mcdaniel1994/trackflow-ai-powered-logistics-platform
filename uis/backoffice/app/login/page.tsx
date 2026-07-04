import type { Metadata } from "next";
import { Suspense } from "react";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Warehouse } from "lucide-react";
import { LoginForm } from "@/components/auth/LoginForm";
import { getServerSessionUser } from "@/lib/auth/session";
import { safeNextPath } from "@/lib/auth/redirects";
import { getPublicWebsiteURL } from "@/lib/public-website";

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
  const publicWebsiteURL = getPublicWebsiteURL();

  if (user?.must_change_password) {
    redirect(`/account/change-password?next=${encodeURIComponent(nextPath)}`);
  }

  if (user) {
    redirect(nextPath);
  }

  return (
    <main className="min-h-screen bg-neutral-50 px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-2xl flex-col justify-center sm:min-h-[calc(100vh-5rem)]">
        <Link
          href={publicWebsiteURL}
          className="mb-5 inline-flex w-fit items-center gap-2 text-sm font-semibold text-navy transition-colors hover:text-coral"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span>Back to TrackFlow website</span>
        </Link>

        <div className="rounded-lg border border-neutral-200 bg-white p-5 shadow-sm sm:p-7">
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
