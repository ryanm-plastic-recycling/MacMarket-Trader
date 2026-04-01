import { ClerkProvider } from "@clerk/nextjs";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body style={{ background: "#10151d", color: "#d7dee8", fontFamily: "Inter, Arial", margin: 0 }}>{children}</body>
      </html>
    </ClerkProvider>
  );
}
