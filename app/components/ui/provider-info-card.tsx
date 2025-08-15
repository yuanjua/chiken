"use client";

import { useState, useRef, ReactNode } from "react";
import { Info } from "lucide-react";

interface InfoCardProps {
  /** Custom title for the info card */
  title?: string;
  /** Custom trigger content */
  trigger?: ReactNode;
  /** Custom width for the popover */
  width?: string;
  /** Compact mode for smaller cards */
  compact?: boolean;
  /** Content to display inside the card */
  children: ReactNode;
}

export function InfoCard({
  title = "Information",
  trigger,
  width = "w-[420px]",
  compact = false,
  children
}: InfoCardProps) {
  const [showInfo, setShowInfo] = useState(false);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = () => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
    setShowInfo(true);
  };

  const handleMouseLeave = () => {
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => setShowInfo(false), 400);
  };

  // Adjust dimensions based on compact mode
  const cardWidth = compact ? "w-[320px]" : width;
  const maxHeight = compact ? "max-h-48" : "max-h-60";
  const padding = compact ? "p-2" : "p-3";
  const headerPadding = compact ? "px-2 py-1" : "px-3 py-2";

  return (
    <div
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {trigger || (
        <Info className={`${compact ? 'h-3 w-3' : 'h-4 w-4'} text-muted-foreground hover:text-foreground cursor-help`} />
      )}
      
      {showInfo && (
        <div
          className={`absolute left-0 mt-2 z-50 ${cardWidth} max-w-[85vw] rounded-md border border-border shadow-lg`}
          style={{
            backgroundColor: "hsl(var(--color-popover))",
            color: "hsl(var(--color-popover-foreground))",
          }}
        >
          {title && (
            <div className={`${headerPadding} border-b ${compact ? 'text-[10px]' : 'text-xs'} font-medium text-muted-foreground`}>
              {title}
            </div>
          )}
          <div className={`${padding} ${maxHeight} overflow-y-auto`}>
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
