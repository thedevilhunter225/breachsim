"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import {
  AUTH_EXPIRED_EVENT,
  getSessionRequest,
  loginRequest,
  logoutRequest,
  refreshSessionRequest,
  SessionData,
} from "@/lib/client-api";

type SessionContextValue = {
  ready: boolean;
  session: SessionData | null;
  signIn: (email: string, password: string, mfaCode?: string) => Promise<SessionData>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);

  useEffect(() => {
    // The bearer is never persisted in browser storage. The API restores the session
    // from a Secure, HttpOnly cookie and returns only the user view needed by the UI.
    void getSessionRequest()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    function clearExpiredSession() {
      setSession(null);
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, clearExpiredSession);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, clearExpiredSession);
  }, []);

  async function signIn(email: string, password: string, mfaCode?: string) {
    const nextSession = await loginRequest(email, password, mfaCode);
    setSession(nextSession);
    return nextSession;
  }

  async function signOut() {
    const hadSession = Boolean(session);
    setSession(null);
    if (hadSession) {
      try {
        await logoutRequest("");
      } catch {
        // Local state is cleared even if the server is temporarily unreachable. The
        // short-lived server session still expires and can be revoked by an administrator.
      }
    }
  }

  useEffect(() => {
    if (!session) return;
    const timer = window.setInterval(() => {
      void refreshSessionRequest().then(setSession).catch(() => setSession(null));
    }, 40 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [session?.user.id]);

  return <SessionContext.Provider value={{ ready, session, signIn, signOut }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return context;
}
