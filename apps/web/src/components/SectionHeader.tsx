export default function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-12 text-center">
      <h2 className="mb-2 text-2xl font-bold tracking-tight sm:text-3xl">
        {title}
      </h2>
      <p className="text-muted">{subtitle}</p>
    </div>
  );
}
