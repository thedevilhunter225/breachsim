import type { Metadata } from "next";
// Type stack: Bricolage Grotesque carries the display voice (variable optical size gives
// headlines real character), IBM Plex Sans supplies institutional/technical body copy, and
// JetBrains Mono handles every number, token and identifier — the forensic-console register.
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import "@fontsource-variable/jetbrains-mono";
import "@/styles/globals.css";
import "@/styles/workspace.css";
import { SessionProvider } from "@/components/session-provider";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: {
    default: "BreachSim | Human Risk Intelligence",
    template: "%s | BreachSim",
  },
  description: "AI-powered phishing simulation, risk intelligence, and adaptive awareness operations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className="min-h-screen antialiased">
        <ThemeProvider>
          <SessionProvider>{children}</SessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
