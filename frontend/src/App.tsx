import { useInstances } from "@/lib/use-instances";
import { useFetch } from "@/lib/use-fetch";
import { api } from "@/lib/api";
import { AppLayout } from "@/components/layout/app-layout";
import { AuthProvider, useAuth, setForceLogout } from "@/lib/auth";
import { LoginPage } from "@/components/login-page";
import { useEffect } from "react";

function AuthGate() {
  const auth = useAuth();

  // Wire up force-logout so the API layer can trigger re-auth on 401
  useEffect(() => {
    setForceLogout(() => {
      window.location.reload();
    });
  }, []);

  // Still checking auth status
  if (auth.user === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  // Not authenticated and login is required
  if (auth.user === false && auth.loginRequired) {
    return <LoginPage />;
  }

  // Authenticated or auth not required
  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  const {
    data: instances,
    loading: instancesLoading,
    error: instancesError,
    refetch: refetchInstances,
    connected: wsConnected,
  } = useInstances();

  const {
    data: leagues,
    loading: leaguesLoading,
  } = useFetch(() => api.leagues());

  return (
    <AppLayout
      instances={instances}
      instancesLoading={instancesLoading}
      instancesError={instancesError}
      leagues={leagues}
      leaguesLoading={leaguesLoading}
      onMutate={refetchInstances}
      wsConnected={wsConnected}
    />
  );
}

export function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
