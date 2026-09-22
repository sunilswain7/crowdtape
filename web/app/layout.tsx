import type { Metadata } from "next";
import "./globals.css";
import Chrome from "@/components/Chrome";

export const metadata: Metadata = {
  title: "Crowdtape — what the crowd is looking at",
  description:
    "The tape is what happened. The crowd is what happens next. Records what people look " +
    "up on CoinMarketCap every ten minutes, and grades its own calls.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" data-accent="blue">
      <head>
        {/* Applied before paint so a light-theme reader never sees a dark flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var d=document.documentElement;
              d.dataset.theme=localStorage.getItem('ct-theme')||'dark';
              d.dataset.accent=localStorage.getItem('ct-accent')||'blue';}catch(e){}`,
          }}
        />
      </head>
      <body>
        <Chrome>{children}</Chrome>
      </body>
    </html>
  );
}
