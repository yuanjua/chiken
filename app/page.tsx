"use client";

import { redirect } from "next/navigation";
import { getStoredLocale } from "@/lib/tauri-store";

export default async function RootRedirect() {
  const locale = await getStoredLocale() || "en";
  redirect(`/${locale}`);
}
