import type { Metadata } from "next";
import { Suspense } from "react";
import { ChangePasswordForm } from "@/components/account/ChangePasswordForm";

export const metadata: Metadata = {
  title: "Change Password - TrackFlow Backoffice",
  description: "Change your TrackFlow Back Office password.",
};

export default function ChangePasswordPage() {
  return (
    <div className="space-y-6">
      <header className="border-b border-mist pb-6">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Account</p>
        <h1 className="mt-2 text-2xl font-black text-navy-deep sm:text-3xl">Change Password</h1>
        <p className="mt-3 max-w-3xl text-neutral-600">
          Update your password before continuing with protected Back Office work.
        </p>
      </header>

      <Suspense fallback={null}>
        <ChangePasswordForm />
      </Suspense>
    </div>
  );
}
