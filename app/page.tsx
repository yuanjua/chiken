"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getStoredLocale } from "@/lib/tauri-store";

export default function RootRedirect() {
  const router = useRouter();

  useEffect(() => {
    async function redirectToLocale() {
      try {
        const locale = await getStoredLocale() || "en";
        router.replace(`/${locale}`);
      } catch (error) {
        console.error("Failed to get stored locale:", error);
        router.replace("/en");
      }
    }
    
    redirectToLocale();
  }, [router]);

  // Show loading or empty div while redirecting
  return <div></div>;
}
