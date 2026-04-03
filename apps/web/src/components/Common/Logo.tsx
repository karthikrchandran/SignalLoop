import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

function LogoMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold text-sm",
        className,
      )}
    >
      EH
    </div>
  )
}

function LogoFull({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-semibold text-base tracking-tight">EngageHub</span>
    </div>
  )
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <LogoFull className={cn("group-data-[collapsible=icon]:hidden", className)} />
        <LogoMark className={cn("hidden group-data-[collapsible=icon]:flex", className)} />
      </>
    ) : variant === "full" ? (
      <LogoFull className={className} />
    ) : (
      <LogoMark className={className} />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
