export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-2">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}
