"use client";

import React, { useEffect, useState } from "react";
import { getCurrentWindow } from '@tauri-apps/api/window';
import { 
  minimizeWindow, 
  toggleMaximizeWindow, 
  closeWindow, 
  isWindowMaximized, 
  getPlatform,
  startDragging
} from "./windowControls";

interface WindowTitlebarProps {
  title?: string;
  className?: string;
}

export default function WindowTitlebar({ 
  title = "", 
  className = "" 
}: WindowTitlebarProps) {
  const [maximized, setMaximized] = useState(false);
  const [currentPlatform, setCurrentPlatform] = useState<string>('unknown');

  useEffect(() => {
    let mounted = true;
    let unlistenResize: (() => void) | undefined;

    const initializeTitlebar = async () => {
      try {
        // Get platform
        const platformName = await getPlatform();
        if (mounted) setCurrentPlatform(platformName);

        // Get initial maximize state
        const isMax = await isWindowMaximized();
        if (mounted) setMaximized(isMax);

        // Listen for window resize events to track maximize state changes
        const appWindow = getCurrentWindow();
        unlistenResize = await appWindow.listen('tauri://resize', async () => {
          if (mounted) {
            const newMaxState = await isWindowMaximized();
            setMaximized(newMaxState);
          }
        });
      } catch (error) {
        console.warn('Failed to initialize titlebar:', error);
      }
    };

    initializeTitlebar();

    return () => {
      mounted = false;
      if (unlistenResize) {
        unlistenResize();
      }
    };
  }, []);

  // Only show custom titlebar on Windows and Linux
  if (currentPlatform !== 'windows' && currentPlatform !== 'linux') {
    return null;
  }

  const handleMinimize = async () => {
    try {
      await minimizeWindow();
    } catch (error) {
      console.warn('Failed to minimize:', error);
    }
  };

  const handleMaximizeRestore = async () => {
    try {
      console.log('Maximize button clicked, current state:', maximized);
      await toggleMaximizeWindow();
      // Update state after toggle
      const newState = await isWindowMaximized();
      console.log('New maximize state:', newState);
      setMaximized(newState);
    } catch (error) {
      console.warn('Failed to toggle maximize/restore:', error);
    }
  };

  const handleClose = async () => {
    try {
      await closeWindow();
    } catch (error) {
      console.warn('Failed to close:', error);
    }
  };

  const handleDoubleClick = () => {
    handleMaximizeRestore();
  };

  // Manual drag region implementation as per Tauri v2 docs
  const handleMouseDown = async (e: React.MouseEvent) => {
    if (e.buttons === 1) { // Primary (left) button
      try {
        if (e.detail === 2) {
          // Double click - toggle maximize
          await toggleMaximizeWindow();
          const newState = await isWindowMaximized();
          setMaximized(newState);
        } else {
          // Single click - start dragging
          await startDragging();
        }
      } catch (error) {
        console.warn('Failed to handle drag/maximize:', error);
      }
    }
  };

  return (
    <div 
      className={`h-7 w-full bg-background flex items-center justify-between fixed top-0 left-0 z-50 ${className}`}
      role="toolbar"
      aria-label="Window Titlebar"
    >
      {/* Left section - App icon and title */}
      <div className="flex items-center h-full px-3">
        <div className="flex items-center gap-2">
          {/* App icon placeholder */}
          <div className="w-4 h-4 rounded bg-primary/10 flex items-center justify-center">
            <div className="w-2 h-2 rounded bg-primary/40" />
          </div>
          <span className="text-xs font-medium text-foreground/70 select-none">
            {title}
          </span>
        </div>
      </div>

      {/* Center section - Draggable area */}
      <div 
        className="flex-1 h-full cursor-move select-none"
        onMouseDown={handleMouseDown}
        role="button"
        tabIndex={-1}
        aria-label="Drag window or double-click to maximize"
      />

      {/* Right section - Window controls */}
      <div className="flex items-center h-full">
        {/* Minimize button */}
        <button
          onClick={handleMinimize}
          className="w-11 h-7 flex items-center justify-center hover:bg-foreground/10 transition-colors group"
          aria-label="Minimize"
          title="Minimize"
        >
          <svg 
            width="10" 
            height="10" 
            viewBox="0 0 10 10" 
            fill="none" 
            className="text-foreground/70 group-hover:text-foreground"
          >
            <path 
              d="M0 5h10" 
              stroke="currentColor" 
              strokeWidth="1" 
            />
          </svg>
        </button>

        {/* Maximize/Restore button */}
        <button
          onClick={handleMaximizeRestore}
          className="w-11 h-7 flex items-center justify-center hover:bg-foreground/10 transition-colors group"
          aria-label={maximized ? "Restore" : "Maximize"}
          title={maximized ? "Restore" : "Maximize"}
        >
          {maximized ? (
            <svg 
              width="10" 
              height="10" 
              viewBox="0 0 10 10" 
              fill="none"
              className="text-foreground/70 group-hover:text-foreground"
            >
              <path 
                d="M2.5 2.5h5v5h-5z" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="1" 
              />
              <path 
                d="M2.5 2.5l1.5-1.5h5v5l-1.5 1.5" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="1" 
              />
            </svg>
          ) : (
            <svg 
              width="10" 
              height="10" 
              viewBox="0 0 10 10" 
              fill="none"
              className="text-foreground/70 group-hover:text-foreground"
            >
              <rect 
                x="1" 
                y="1" 
                width="8" 
                height="8" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="1" 
              />
            </svg>
          )}
        </button>

        {/* Close button */}
        <button
          onClick={handleClose}
          className="w-11 h-7 flex items-center justify-center hover:bg-red-500 hover:text-white transition-colors group"
          aria-label="Close"
          title="Close"
        >
          <svg 
            width="10" 
            height="10" 
            viewBox="0 0 10 10" 
            fill="none"
            className="text-foreground/70 group-hover:text-white"
          >
            <path 
              d="M1 1l8 8M1 9l8-8" 
              stroke="currentColor" 
              strokeWidth="1" 
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
