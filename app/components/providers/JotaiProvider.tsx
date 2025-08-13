"use client";

import { Provider } from "jotai";
import { store } from "@/lib/store";
import { SessionInitializer } from "./SessionInitializer";

export function JotaiProvider({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <SessionInitializer />
      {children}
    </Provider>
  );
}
