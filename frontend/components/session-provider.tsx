"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";

import { AUTH_EXPIRED_EVENT, loginRequest, SessionData } from "@/lib/client-api";

const SESSION_STORAGE_KEY = "breachsim.session";

type SessionContextValue = {
  ready: boolean;
  session: SessionData | null;
  signIn: (email: string, password: string) => Promise<SessionData>;
  signOut: () => void;
};

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

function isExpired(session: SessionData) {
  try {
    const [, payload] = session.access_token.split(".");
    const decoded = JSON.parse(window.atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: number };
    return typeof decoded.exp === "number" && decoded.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (raw) {
      try {
        const storedSession = JSON.parse(raw) as SessionData;
        if (isExpired(storedSession)) {
          window.localStorage.removeItem(SESSION_STORAGE_KEY);
        } else {
          setSession(storedSession);
        }
      } catch {
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
      }
    }
    setReady(true);
  }, []);

  useEffect(() => {
    function clearExpiredSession() {
      setSession(null);
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, clearExpiredSession);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, clearExpiredSession);
  }, []);

  async function signIn(email: string, password: string) {
    const nextSession = await loginRequest(email, password);
    setSession(nextSession);
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSession));
    return nextSession;
  }

  function signOut() {
    setSession(null);
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  return <SessionContext.Provider value={{ ready, session, signIn, signOut }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return context;
}
