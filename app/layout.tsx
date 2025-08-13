import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { JotaiProvider } from "@/components/providers/JotaiProvider";

import AppLayout from "@/components/layout/AppLayout";

export const metadata = {
  title: "ChiKen",
  description: "ChiKen is an AI reseacher assistant.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="font-sans h-full overflow-hidden">
        <JotaiProvider>
          <ThemeProvider>
            <AppLayout>{children}</AppLayout>
            <Toaster />
          </ThemeProvider>
        </JotaiProvider>
      </body>
    </html>
  );
}
