import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  tone?: "default" | "inverse"
  className?: string
  asLink?: boolean
}

function LogoMark({
  className,
  tone = "default",
}: {
  className?: string
  tone?: LogoProps["tone"]
}) {
  return (
    <div
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded-md font-bold text-sm",
        tone === "inverse"
          ? "bg-white/14 text-white ring-1 ring-white/20"
          : "bg-primary text-primary-foreground",
        className,
      )}
    >
      EH
    </div>
  )
}

function LogoFull({
  className,
  tone = "default",
}: {
  className?: string
  tone?: LogoProps["tone"]
}) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <LogoMark tone={tone} />
      <span
        className={cn(
          "font-semibold text-base",
          tone === "inverse" ? "text-white" : "text-foreground",
        )}
      >
        SignalLoop
      </span>
    </div>
  )
}

export function Logo({
  variant = "full",
  tone = "default",
  className,
  asLink = true,
}: LogoProps) {
  const content =
    variant === "responsive" ? (
      <>
        <LogoFull
          tone={tone}
          className={cn("group-data-[collapsible=icon]:hidden", className)}
        />
        <LogoMark
          tone={tone}
          className={cn("hidden group-data-[collapsible=icon]:flex", className)}
        />
      </>
    ) : variant === "full" ? (
      <LogoFull tone={tone} className={className} />
    ) : (
      <LogoMark tone={tone} className={className} />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
