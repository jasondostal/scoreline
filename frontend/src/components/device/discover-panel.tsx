import { useState } from "react";
import { api } from "@/lib/api";
import type { DiscoveredDevice } from "@/lib/types";
import { Wifi, Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DiscoverPanelProps {
  onMutate: () => void;
}

export function DiscoverPanel({ onMutate }: DiscoverPanelProps) {
  const [scanning, setScanning] = useState(false);
  const [devices, setDevices] = useState<DiscoveredDevice[] | null>(null);

  const handleScan = async () => {
    setScanning(true);
    try {
      const found = await api.discover();
      setDevices(found);
    } catch {
      setDevices([]);
    } finally {
      setScanning(false);
    }
  };

  const handleAdd = async (device: DiscoveredDevice) => {
    await api.addDevice(device.ip, 0, 0);
    onMutate();
    // Refresh scan results
    handleScan();
  };

  return (
    <div>
      <Button variant="outline" size="xs" onClick={handleScan} disabled={scanning}>
        {scanning ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <Wifi className="h-3 w-3" />
        )}
        Scan Network
      </Button>

      {devices !== null && (
        <div className="mt-2 rounded border border-armed/20 bg-armed/5 p-2">
          <div className="mb-1 text-[11px] font-semibold text-armed">
            Discovered on network:
          </div>
          {devices.length === 0 ? (
            <div className="text-[11px] text-muted-foreground">
              No WLED devices found.
            </div>
          ) : (
            <div className="space-y-1">
              {devices.map((d) => (
                <div
                  key={d.mac || d.ip}
                  className="flex items-center justify-between text-xs"
                >
                  <span>
                    <span className="font-medium">{d.name}</span>
                    <span className="ml-2 font-mono text-muted-foreground">
                      {d.ip}
                    </span>
                  </span>
                  {d.configured ? (
                    <span className="text-[10px] text-muted-foreground">
                      Already added
                    </span>
                  ) : (
                    <Button
                      size="xs"
                      className="h-5 bg-armed px-2 text-[10px] hover:bg-armed/90"
                      onClick={() => handleAdd(d)}
                    >
                      <Plus className="h-2.5 w-2.5" />
                      Add
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
