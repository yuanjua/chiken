"use client";

import { useEffect } from "react";
import { useAtom } from "jotai";
import { themeAtom } from "@/store/uiAtoms";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme] = useAtom(themeAtom);

  useEffect(() => {
    // Use globalThis.window to avoid TypeScript errors and ensure browser-only DOM access
    const win = (typeof globalThis !== "undefined" && (globalThis as any).window) ? (globalThis as any).window : undefined;
    if (!win) return;
    const root = win.document.documentElement;

    // Remove all theme classes
    root.classList.remove("light", "dark");

    let appliedTheme = theme;
    if (theme === "system") {
      appliedTheme = win.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }

    // Add the theme class
    root.classList.add(appliedTheme);

    // Set color scheme for better browser integration
    root.style.colorScheme = appliedTheme;

    // Force a repaint to ensure styles are applied immediately
    root.style.display = "none";
    const _forceReflow = root.offsetHeight; // Trigger reflow
    root.style.display = "";
  }, [theme]);

  // Listen for system theme changes
  useEffect(() => {
    // Use globalThis.window to avoid TypeScript errors
    const win = (typeof globalThis !== "undefined" && (globalThis as any).window) ? (globalThis as any).window : undefined;
    if (theme === "system" && win) {
      const mediaQuery = win.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = () => {
        const root = win.document.documentElement;
        root.classList.remove("light", "dark");
        const newTheme = mediaQuery.matches ? "dark" : "light";
        root.classList.add(newTheme);
        root.style.colorScheme = newTheme;
      };

      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [theme]);

  return <>{children}</>;
}
