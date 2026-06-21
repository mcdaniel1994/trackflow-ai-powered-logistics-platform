"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AUTH_SESSION_EXPIRED_EVENT } from "@/lib/auth/constants";
import { getMe, logout as logoutRequest } from "@/lib/auth/api";
import { loginPathFor } from "@/lib/auth/redirects";
import type { AuthUser } from "@/lib/auth/types";

type AuthContextValue = {
  user: AuthUser;
  setUser: (user: AuthUser) => void;
  refreshUser: () => Promise<AuthUser | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  initialUser,
  children,
}: {
  initialUser: AuthUser;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState(initialUser);

  const handleExpired = useCallback(() => {
    router.replace(loginPathFor(`${window.location.pathname}${window.location.search}`));
    router.refresh();
  }, [router]);

  useEffect(() => {
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleExpired);
  }, [handleExpired]);

  const refreshUser = useCallback(async () => {
    try {
      const nextUser = await getMe();
      setUser(nextUser);
      return nextUser;
    } catch {
      handleExpired();
      return null;
    }
  }, [handleExpired]);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      setUser,
      refreshUser,
      logout,
    }),
    [logout, refreshUser, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return context;
}
