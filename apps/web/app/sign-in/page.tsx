import { SignIn } from "@clerk/nextjs";

export default function Page() {
  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100vh", padding: 24 }}>
      <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" forceRedirectUrl="/dashboard" />
    </main>
  );
}
