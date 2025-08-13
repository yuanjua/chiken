import { NextIntlClientProvider } from "next-intl";
import "../globals.css";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { JotaiProvider } from "@/components/providers/JotaiProvider";
import AppLayout from "@/components/layout/AppLayout";

export const metadata = {
  title: "ChiKen",
  description: "ChiKen is an AI reseacher assistant.",
};

export const dynamic = "force-static";

export const locales = ["en", "zh"] as const;

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = (await import(`../../messages/${locale}.json`)).default;
  const isRtl = ["ar", "he", "fa", "ur"].includes(locale);

  return (
    <div dir={isRtl ? "rtl" : "ltr"} className="h-full">
      <NextIntlClientProvider locale={locale} messages={messages}>
        <JotaiProvider>
          <ThemeProvider>
            <AppLayout>{children}</AppLayout>
            <Toaster />
          </ThemeProvider>
        </JotaiProvider>
      </NextIntlClientProvider>
    </div>
  );
}


