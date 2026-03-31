export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: "#10151d", color: "#d7dee8", fontFamily: "Inter, Arial", margin: 0 }}>
        <main style={{ padding: 24 }}>{children}</main>
      </body>
    </html>
  );
}
