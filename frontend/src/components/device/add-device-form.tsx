import { useState } from "react";
import { api } from "@/lib/api";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AddDeviceFormProps {
  onMutate: () => void;
}

export function AddDeviceForm({ onMutate }: AddDeviceFormProps) {
  const [open, setOpen] = useState(false);
  const [host, setHost] = useState("");
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!host) return;
    setSubmitting(true);
    try {
      await api.addDevice(host, start, end);
      setHost("");
      setStart(0);
      setEnd(0);
      setOpen(false);
      onMutate();
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <Button variant="outline" size="xs" onClick={() => setOpen(true)}>
        <Plus className="h-3 w-3" />
        Add WLED
      </Button>
    );
  }

  return (
    <div className="rounded border border-live/30 bg-live/5 p-3">
      <div className="mb-2 text-[11px] font-semibold text-live">
        Add WLED Device
      </div>
      <div className="mb-2 flex flex-wrap gap-2">
        <input
          type="text"
          value={host}
          onChange={(e) => setHost(e.target.value)}
          placeholder="IP / Hostname"
          className="min-w-[120px] flex-[2] rounded border border-input bg-secondary px-2 py-1.5 text-xs text-foreground"
        />
        <input
          type="number"
          value={start}
          onChange={(e) => setStart(Number(e.target.value))}
          placeholder="Start"
          className="w-20 rounded border border-input bg-secondary px-2 py-1.5 text-xs text-foreground"
        />
        <input
          type="number"
          value={end}
          onChange={(e) => setEnd(Number(e.target.value))}
          placeholder="End"
          className="w-20 rounded border border-input bg-secondary px-2 py-1.5 text-xs text-foreground"
        />
      </div>
      <div className="flex gap-2">
        <Button size="xs" className="bg-live hover:bg-live/90" onClick={handleSubmit} disabled={!host || submitting}>
          Add
        </Button>
        <Button variant="outline" size="xs" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
