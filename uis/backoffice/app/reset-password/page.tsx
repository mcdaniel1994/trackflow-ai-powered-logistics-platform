import type { Metadata } from "next";
import Link from "next/link";
import { Warehouse } from "lucide-react";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset Password - TrackFlow Backoffice",
  description: "Choose a new TrackFlow Back Office password.",
};

type ResetPasswordPageProps = {
  searchParams?: Promise<{
    token?: string;
  }>;
};

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const params = (await searchParams) ?? {};
  const token = params.token ?? "";

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
              <h1 className="text-2xl font-black text-navy-deep">Set new password</h1>
            </div>
          </div>
          <ResetPasswordForm token={token} />
          <div className="mt-5 border-t border-neutral-200 pt-4">
            <Link href="/login" className="text-sm font-semibold text-navy hover:text-coral">
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
