export function ConsolePage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <section>
      <h1 style={{ fontSize: 24, marginBottom: 8, textTransform: "capitalize" }}>{title}</h1>
      <p style={{ color: "#9fb0c3", marginTop: 0 }}>{subtitle}</p>
    </section>
  );
}
