import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getSportIcon } from "@/lib/sport-icons";
import type { League } from "@/lib/types";

interface LeagueSelectProps {
  leagues: League[];
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function LeagueSelect({
  leagues,
  value,
  onValueChange,
  placeholder = "League...",
  disabled,
  className,
}: LeagueSelectProps) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger size="sm" className={`h-8 text-xs bg-secondary border-input ${className ?? ""}`}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {leagues.map((l) => {
          const Icon = getSportIcon(l.sport);
          return (
            <SelectItem key={l.id} value={l.id}>
              <span className="flex items-center gap-2">
                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                {l.name}
              </span>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
