"use client";

import { ExternalLink } from "lucide-react";
import { InfoCard } from "@/components/ui/provider-info-card";

interface ProviderItem {
  name: string;
  url: string;
  description: string;
}

interface ProviderInfoCardProps {
  /** List of providers to display */
  providers?: ProviderItem[];
  /** Custom title for the providers card */
  title?: string;
  /** Custom trigger content */
  trigger?: React.ReactNode;
  /** Custom width for the popover */
  width?: string;
  /** Compact mode for smaller cards */
  compact?: boolean;
}

const defaultProviders: ProviderItem[] = [
  {
    name: "Ollama",
    url: "https://ollama.com",
    description: ""
  },
  {
    name: "vLLM",
    url: "https://github.com/vllm-project/vllm",
    description: ""
  },
  {
    name: "LM Studio",
    url: "https://lmstudio.ai",
    description: ""
  },
];

export function ProviderInfoCard({
  providers = defaultProviders,
  title = "Popular Local Model Providers",
  trigger,
  width = "w-[420px]",
  compact = false,
}: ProviderInfoCardProps) {
  const spacing = compact ? "space-y-2" : "space-y-3";

  return (
    <InfoCard
      title={title}
      trigger={trigger}
      width={width}
      compact={compact}
    >
      <div className={spacing}>
        {providers.map((provider, index) => (
          <div key={index} className={compact ? "space-y-1" : "space-y-2"}>
            <div className="flex items-center justify-between">
              <span className={`${compact ? 'text-xs' : 'text-sm'} font-medium`}>
                {provider.name}
              </span>
              <a
                href={provider.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-1 ${compact ? 'text-[10px]' : 'text-xs'} text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300`}
              >
                <ExternalLink className={compact ? "h-2 w-2" : "h-3 w-3"} />
                {provider.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            </div>
            <p className={`${compact ? 'text-[10px]' : 'text-xs'} text-muted-foreground`}>
              {provider.description}
            </p>
          </div>
        ))}
      </div>
    </InfoCard>
  );
}
