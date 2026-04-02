import { ClerkProvider } from "@clerk/nextjs";
import { cookies } from "next/headers";

import "./globals.css";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  const cookieStore = await cookies();
  const themeCookie = cookieStore.get("macmarket-theme")?.value;
  const initialTheme = themeCookie === "light" ? "light" : "dark";
  return (
    <html lang="en" data-theme={initialTheme}>
      <body>
        {publishableKey ? <ClerkProvider publishableKey={publishableKey}>{children}</ClerkProvider> : children}
      </body>
    </html>
  );
}
