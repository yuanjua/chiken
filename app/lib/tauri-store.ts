"use client";

import { load } from '@tauri-apps/plugin-store';

let store: Awaited<ReturnType<typeof load>> | null = null;

const initStore = async () => {
  if (!store) {
    store = await load('settings.json', { autoSave: true });
  }
  return store;
};

export const getStoredLocale = async (): Promise<string | null> => {
  try {
    const s = await initStore();
    return await s.get('locale') as string | null;
  } catch {
    return null;
  }
};

export const setStoredLocale = async (locale: string): Promise<void> => {
  try {
    const s = await initStore();
    await s.set('locale', locale);
  } catch {
    // Silent fail
  }
};

export const getStoredTheme = async (): Promise<string | null> => {
  try {
    const s = await initStore();
    return await s.get('theme') as string | null;
  } catch {
    return null;
  }
};

export const setStoredTheme = async (theme: string): Promise<void> => {
  try {
    const s = await initStore();
    await s.set('theme', theme);
  } catch {
    // Silent fail
  }
};
