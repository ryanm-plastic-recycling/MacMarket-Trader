import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 24 }}>
      <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" forceRedirectUrl="/dashboard" />
    </main>
  );
}
