import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata = {
  title: "ProductOlogy: see what your client forks can do",
  description: "A product-level map of every client fork: what it adds, what it changes, why it was built, and what belongs back in your main product.",
  openGraph: {
    title: "ProductOlogy: see what your client forks can do",
    description: "A product-level map of every client fork: what it adds, what it changes, why it was built, and what belongs back in your main product.",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
