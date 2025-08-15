"use client";

import { InfoCard } from "@/components/ui/provider-info-card";

interface EnvVarItem {
  name: string;
  description?: string;
}

interface EnvVarInfoCardProps {
  /** List of environment variables to display */
  envVars?: EnvVarItem[];
  /** Custom title for the env vars card */
  title?: string;
  /** Custom trigger content */
  trigger?: React.ReactNode;
  /** Compact mode for smaller cards */
  compact?: boolean;
}

export function EnvVarInfoCard({
  envVars = [],
  title = "Recommended Environment Variables",
  trigger,
  compact = true,
}: EnvVarInfoCardProps) {
  const width = compact ? "w-[360px]" : "w-[420px]";

  return (
    <InfoCard
      title={title}
      trigger={trigger}
      width={width}
      compact={compact}
    >
      {envVars.length > 0 ? (
        <table className="w-full text-xs">
          <colgroup>
            <col style={{ width: '45%' }} />
            <col style={{ width: '55%' }} />
          </colgroup>
          <tbody>
            {envVars.map((envVar) => (
              <tr key={envVar.name} className="border-b last:border-b-0">
                <td className="py-1 pr-2 align-top font-mono text-[11px] text-muted-foreground">
                  {envVar.name}
                </td>
                <td className="py-1 align-top text-[11px]">
                  {envVar.description || ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          No recommendations available.
        </p>
      )}
    </InfoCard>
  );
}
