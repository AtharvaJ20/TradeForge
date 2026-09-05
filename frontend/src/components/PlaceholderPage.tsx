interface PlaceholderPageProps {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-12">
      <div className="text-center">
        <h1 className="mb-2 text-xl font-semibold text-text-primary">{title}</h1>
        <p className="text-sm text-text-secondary">Coming soon</p>
      </div>
    </div>
  )
}
