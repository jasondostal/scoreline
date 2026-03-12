import { createContext, useCallback, useContext, useEffect, useState } from "react";

interface AuthState {
  /** null = still checking, false = not authenticated, string = username */
  user: string | null | false;
  loginRequired: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<string | null | false>(null);
  const [loginRequired, setLoginRequired] = useState(false);

  // Check auth status on mount
  useEffect(() => {
    fetch("/api/auth/me")
      .then((res) => res.json())
      .then((data) => {
        if (data.authenticated) {
          setUser(data.user);
        } else {
          setUser(false);
          setLoginRequired(data.login_required ?? false);
        }
      })
      .catch(() => setUser(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || `${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    setUser(false);
    setLoginRequired(true);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loginRequired, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Call this from the API layer to force re-auth on 401 */
let _forceLogout: (() => void) | null = null;

export function setForceLogout(fn: () => void) {
  _forceLogout = fn;
}

export function triggerForceLogout() {
  _forceLogout?.();
}
