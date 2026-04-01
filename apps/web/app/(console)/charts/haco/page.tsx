import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { HacoWorkspace } from "@/components/charts/haco-workspace";

export default async function Page() {
  const { getToken, userId } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }
  const token = (await getToken()) ?? "user-token";

  return <HacoWorkspace token={token} />;
}
