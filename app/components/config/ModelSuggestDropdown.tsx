import React, { useState, useRef, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Loader2, Search } from "lucide-react";

interface ModelSuggestion {
  id: string;
  name: string;
  cost_info?: {
    input_cost_per_token?: number;
    output_cost_per_token?: number;
  };
}

interface ModelSuggestDropdownProps {
  provider: string;
  baseUrl?: string;
  value: string;
  onChange: (value: string) => void;
  onModelSelect: (model: string) => void;
  fetchSuggestions: (input: string) => Promise<ModelSuggestion[]>;
  disabled?: boolean;
  placeholder?: string;
  renderCostInfo?: (costInfo: any) => React.ReactNode;
}

export const ModelSuggestDropdown: React.FC<ModelSuggestDropdownProps> = ({
  provider,
  baseUrl,
  value,
  onChange,
  onModelSelect,
  fetchSuggestions,
  disabled,
  placeholder,
  renderCostInfo,
}) => {
  // Helper to get model part (after first slash)
  const getModelPart = (fullName: string) => {
    if (!fullName) return "";
    // Only strip the provider prefix (e.g., 'ollama/') if present
    if (provider && fullName.startsWith(provider + "/")) {
      return fullName.slice(provider.length + 1);
    }
    return fullName;
  };

  // Local state for the input display value (model part only)
  const [inputValue, setInputValue] = useState(getModelPart(value));
  const [suggestions, setSuggestions] = useState<ModelSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Sync inputValue with value from parent (e.g., after select)
  useEffect(() => {
    setInputValue(getModelPart(value));
  }, [value]);

  // Debounced suggestion fetching
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (inputValue.trim() && showSuggestions && !disabled) {
        setLoadingSuggestions(true);
        fetchSuggestions(inputValue.trim())
          .then((results) => {
            setSuggestions(results);
            setSelectedSuggestionIndex(-1);
          })
          .catch(() => setSuggestions([]))
          .finally(() => setLoadingSuggestions(false));
      } else {
        setSuggestions([]);
      }
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [inputValue, showSuggestions, fetchSuggestions, disabled]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const modelPart = e.target.value;
    setInputValue(modelPart);
    setShowSuggestions(true);
    setSelectedSuggestionIndex(-1);
    // Always add provider prefix for config
    let fullValue = modelPart;
    if (provider && fullValue && !fullValue.startsWith(provider + "/")) {
      fullValue = `${provider}/${fullValue}`;
    }
    onChange(fullValue);
  };

  const handleSuggestionSelect = (suggestion: ModelSuggestion) => {
    setInputValue(getModelPart(suggestion.name));
    setShowSuggestions(false);
    onChange(suggestion.name);
    onModelSelect(suggestion.name);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedSuggestionIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedSuggestionIndex((prev) =>
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case "Enter":
        e.preventDefault();
        if (selectedSuggestionIndex >= 0) {
          handleSuggestionSelect(suggestions[selectedSuggestionIndex]);
        } else {
          setShowSuggestions(false);
          // Always add provider prefix for config
          let fullValue = inputValue;
          if (provider && fullValue && !fullValue.startsWith(provider + "/")) {
            fullValue = `${provider}/${fullValue}`;
          }
          onChange(fullValue);
          onModelSelect(fullValue);
        }
        break;
      case "Escape":
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
        break;
    }
  };

  const handleInputBlur = () => {
    setTimeout(() => {
      setShowSuggestions(false);
      setSelectedSuggestionIndex(-1);
      // On blur, always reset inputValue to the model part of the last value
      setInputValue(getModelPart(value));
    }, 200);
  };

  const handleInputFocus = () => {
    if (inputValue.trim()) {
      setShowSuggestions(true);
    }
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleInputKeyDown}
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
        placeholder={placeholder}
        disabled={disabled}
        className="pr-8"
      />
      {loadingSuggestions && (
        <Loader2 className="w-4 h-4 animate-spin absolute right-2 top-1/2 transform -translate-y-1/2" />
      )}
      {showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute z-50 w-full mt-1 border border-border rounded-md shadow-lg max-h-60 overflow-y-auto text-popover-foreground"
          style={{
            backgroundColor: "hsl(var(--color-popover))",
            color: "hsl(var(--color-popover-foreground))"
          }}
        >
          {suggestions.map((suggestion, index) => (
            <div
              key={suggestion.id}
              className={`px-3 py-2 cursor-pointer hover:bg-accent hover:text-accent-foreground ${
                index === selectedSuggestionIndex ? "bg-accent text-accent-foreground" : ""
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                handleSuggestionSelect(suggestion);
              }}
            >
              <div className="flex flex-col">
                <span className="font-medium text-sm">{suggestion.name}</span>
                {renderCostInfo && renderCostInfo(suggestion.cost_info)}
              </div>
            </div>
          ))}
          <div 
            className="px-3 py-2 text-xs text-muted-foreground border-t"
            style={{
              backgroundColor: "hsl(var(--color-popover))",
              borderTopColor: "hsl(var(--color-border))"
            }}
          >
            <div className="flex items-center gap-1">
              <Search className="w-3 h-3" />
              Press Enter to use &quot;{inputValue}&quot; or select a suggestion
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
