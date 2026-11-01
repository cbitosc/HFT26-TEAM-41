import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HFT26 Team 41",
  description: "Development dashboard",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
