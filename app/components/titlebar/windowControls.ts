/**
 * Window controls utilities for Tauri
 * Provides safe window management functions with fallbacks
 */

import { getCurrentWindow } from '@tauri-apps/api/window';
import { platform } from '@tauri-apps/plugin-os';

declare const window: Window & { navigator: Navigator };

export async function getPlatform(): Promise<string> {
  try {
    return await platform();
  } catch {
    // Fallback detection using window object (client-side only)
    if (typeof window !== 'undefined' && window.navigator) {
      const userAgent = window.navigator.userAgent.toLowerCase();
      if (userAgent.includes('win')) return 'windows';
      if (userAgent.includes('mac')) return 'macos';
      if (userAgent.includes('linux')) return 'linux';
    }
    return 'unknown';
  }
}

export async function minimizeWindow(): Promise<void> {
  try {
    const appWindow = getCurrentWindow();
    await appWindow.minimize();
  } catch (error) {
    console.warn('Failed to minimize window:', error);
  }
}

export async function toggleMaximizeWindow(): Promise<void> {
  try {
    const appWindow = getCurrentWindow();
    await appWindow.toggleMaximize();
    console.log('Toggle maximize called successfully');
  } catch (error) {
    console.warn('Failed to toggle maximize:', error);
  }
}

export async function closeWindow(): Promise<void> {
  try {
    const appWindow = getCurrentWindow();
    await appWindow.close();
  } catch (error) {
    console.warn('Failed to close window:', error);
  }
}

export async function isWindowMaximized(): Promise<boolean> {
  try {
    const appWindow = getCurrentWindow();
    return await appWindow.isMaximized();
  } catch (error) {
    console.warn('Failed to check if window is maximized:', error);
    return false;
  }
}

export async function startDragging(): Promise<void> {
  try {
    const appWindow = getCurrentWindow();
    await appWindow.startDragging();
  } catch (error) {
    console.warn('Failed to start dragging:', error);
  }
}
