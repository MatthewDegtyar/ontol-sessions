import "./globals.css";

export const metadata = {
  title: "ontol: what did we build for this client, and why?",
  description: "Link AI coding sessions to tickets, so people and agents can find the reasoning behind client work.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
