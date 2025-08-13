import React, { useState, useEffect, useRef } from "react";
import { Input } from "@/components/ui/input";
import { getAvailableProviders } from "@/lib/api-client";
import { Label } from "@/components/ui/label";

interface ProviderSelectProps {
  value: string;
  onChange: (provider: string) => void;
  label?: string;
  disabled?: boolean;
  placeholder?: string;
}

export function ProviderSelect({ value, onChange, label, disabled, placeholder }: ProviderSelectProps) {
  const [input, setInput] = useState(value || "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasInteracted = useRef(false); // fix: dropdown menu opened by default

  useEffect(() => {
    setInput(value || "");
  }, [value]);

  useEffect(() => {
    setLoading(true);
    getAvailableProviders().then(data => {
      setSuggestions(data.providers.map(p => p.id));
      setLoading(false);
    });
  }, []);

  const filtered = input
    ? suggestions.filter(s => s.toLowerCase().includes(input.toLowerCase()))
    : suggestions;

  return (
    <div style={{ position: "relative" }}>
      {label && <Label htmlFor="provider-select-input">{label}</Label>}
      <Input
        id="provider-select-input"
        ref={inputRef}
        value={input}
        onChange={e => {
          setInput(e.target.value);
          onChange(e.target.value);
          setShowDropdown(true);
          hasInteracted.current = true;
        }}
        onClick={() => {
          setShowDropdown(true);
          hasInteracted.current = true;
        }}
        onBlur={() => setTimeout(() => setShowDropdown(false), 100)}
        disabled={disabled}
        placeholder={placeholder || "Type provider name..."}
        autoComplete="off"
        className="font-mono text-sm"
      />
      {showDropdown && filtered.length > 0 && (
        <ul
          className="absolute z-10 w-full max-h-44 overflow-y-auto mt-1 rounded-md border border-border shadow-lg"
          style={{ backgroundColor: "hsl(var(--color-popover))", color: "hsl(var(--color-popover-foreground))" }}
        >
          {filtered.map(s => (
            <li
              key={s}
              className={`px-3 py-2 cursor-pointer hover:bg-muted dark:hover:bg-muted ${s === input ? "bg-muted dark:bg-muted" : ""}`}
              onMouseDown={() => {
                setInput(s);
                onChange(s);
                setShowDropdown(false);
                inputRef.current?.blur();
              }}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
      {loading && <div className="text-xs text-muted-foreground mt-1">Loading providers...</div>}
    </div>
  );
}
