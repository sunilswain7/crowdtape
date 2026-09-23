import type { Metadata } from "next";
import "./globals.css";
import Chrome from "@/components/Chrome";

const SITE = "https://sunilswain7.github.io/crowdtape";
const DESC =
  "CoinMarketCap knows which coins people look up before they buy, and keeps no history " +
  "of it. Crowdtape records it every ten minutes, reads it against price and leverage, " +
  "and grades every call it makes.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    default: "Crowdtape — what the crowd is looking at",
    template: "%s · Crowdtape",
  },
  description: DESC,
  applicationName: "Crowdtape",
  icons: { icon: "/icon.svg", apple: "/apple-icon.png" },
  openGraph: {
    title: "Crowdtape — the tape is what happened, the crowd is what happens next",
    description: DESC,
    url: SITE,
    siteName: "Crowdtape",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Crowdtape — what the crowd is looking at",
    description: DESC,
    images: ["/og.png"],
  },
};

export const viewport = { themeColor: "#0b0c0e" };

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
