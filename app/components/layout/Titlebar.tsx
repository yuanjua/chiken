"use client";

export default function Titlebar() {
  return (
    <div 
      data-tauri-drag-region
      className="h-7 w-full bg-background flex items-center justify-center fixed top-0 left-0 z-50"
    >
      {/* Empty titlebar - draggable area */}
    </div>
  );
}
