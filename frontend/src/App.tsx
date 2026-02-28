import { usePoll } from "@/lib/use-poll";
import { useFetch } from "@/lib/use-fetch";
import { api } from "@/lib/api";
import { POLL_INTERVAL_MS } from "@/lib/constants";
import { AppLayout } from "@/components/layout/app-layout";

export function App() {
  const {
    data: instances,
    loading: instancesLoading,
    error: instancesError,
    refetch: refetchInstances,
  } = usePoll(() => api.instances(), POLL_INTERVAL_MS);

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
    />
  );
}
