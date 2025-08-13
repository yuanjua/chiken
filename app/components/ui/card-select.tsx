import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface CardSelectOption {
  id: string;
  label: string;
  icon?: React.ReactNode;
  description?: string;
}

interface CardSelectProps {
  options: CardSelectOption[];
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  disabled?: boolean;
}

export function CardSelect({
  options,
  value,
  onValueChange,
  className,
  disabled = false,
}: CardSelectProps) {
  const [selectedValue, setSelectedValue] = useState(value || options[0]?.id);

  const handleSelect = (optionId: string) => {
    if (disabled) return;
    setSelectedValue(optionId);
    onValueChange?.(optionId);
  };

  return (
    <div className={cn("flex gap-2", className)}>
      {options.map((option) => {
        const isSelected = selectedValue === option.id;
        return (
          <Card
            key={option.id}
            className={cn(
              "cursor-pointer transition-all hover:shadow-md",
              isSelected
                ? "ring-2 ring-primary bg-primary/5"
                : "hover:bg-muted/50",
              disabled && "opacity-50 cursor-not-allowed"
            )}
            onClick={() => handleSelect(option.id)}
          >
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                {option.icon && (
                  <div className="flex-shrink-0">{option.icon}</div>
                )}
                <div className="flex-1">
                  <div className="font-medium text-sm">{option.label}</div>
                  {option.description && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {option.description}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
} 