import type { Metadata } from "next";
import { ProfileForm } from "@/components/account/ProfileForm";

export const metadata: Metadata = {
  title: "Account Profile - TrackFlow Backoffice",
  description: "View and update your TrackFlow Back Office profile.",
};

export default function ProfilePage() {
  return (
    <div className="space-y-6">
      <header className="border-b border-mist pb-6">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-coral">Account</p>
        <h1 className="mt-2 text-2xl font-black text-navy-deep sm:text-3xl">Profile</h1>
        <p className="mt-3 max-w-3xl text-neutral-600">
          Manage the safe account details used by the Back Office.
        </p>
      </header>

      <ProfileForm />
    </div>
  );
}
