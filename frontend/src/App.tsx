import { useInstances } from "@/lib/use-instances";
import { useFetch } from "@/lib/use-fetch";
import { api } from "@/lib/api";
import { AppLayout } from "@/components/layout/app-layout";

export function App() {
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
