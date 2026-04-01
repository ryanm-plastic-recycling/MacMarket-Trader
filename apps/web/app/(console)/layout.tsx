import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { ConsoleShell } from "@/components/console-shell";

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }
  return <ConsoleShell>{children}</ConsoleShell>;
}
