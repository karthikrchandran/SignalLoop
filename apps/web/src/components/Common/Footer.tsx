export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t border-border/70 px-4 py-3 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>(c) {currentYear} SignalLoop</p>
        <p>Campaigns, voice, email, and account workflows</p>
      </div>
    </footer>
  )
}
