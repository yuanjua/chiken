import "./globals.css";
import { ClientProviders } from "@/components/providers/ClientProviders";

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
        <ClientProviders>
          {children}
        </ClientProviders>
      </body>
    </html>
  );
}
