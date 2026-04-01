"use client";

import { useEffect, useState } from "react";

export default function Page() {
  const [user, setUser] = useState<any>(null);
  useEffect(() => { fetch("/api/user/me", { cache: "no-store" }).then((r) => r.json()).then(setUser); }, []);

  return <section><h1>Account</h1>
    <div>Email: {user?.email ?? "-"}</div>
    <div>Approval status: {user?.approval_status ?? "-"}</div>
    <div>Role: {user?.app_role ?? "-"}</div>
    <div>MFA enabled: {String(user?.mfa_enabled ?? false)}</div>
  </section>;
}
