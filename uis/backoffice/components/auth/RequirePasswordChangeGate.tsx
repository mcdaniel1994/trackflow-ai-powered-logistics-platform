"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth/context";

export function RequirePasswordChangeGate({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (!user.must_change_password || pathname === "/account/change-password") {
      return;
    }

    const current = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
    router.replace(`/account/change-password?next=${encodeURIComponent(current)}`);
  }, [pathname, router, searchParams, user.must_change_password]);

  if (user.must_change_password && pathname !== "/account/change-password") {
    return null;
  }

  return children;
}
