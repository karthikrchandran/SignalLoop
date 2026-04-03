import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="bg-primary/5 dark:bg-zinc-900 relative hidden lg:flex lg:flex-col lg:items-center lg:justify-center gap-6 p-12">
        <Logo variant="full" asLink={false} />
        <div className="text-center max-w-sm">
          <h2 className="text-2xl font-semibold tracking-tight">Intelligent Outreach, Simplified</h2>
          <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
            Reach your audience across email and voice channels — with AI-driven
            personalisation, prebuilt sequences, and real-time analytics in one
            platform.
          </p>
        </div>
        <ul className="mt-2 space-y-2 text-sm text-muted-foreground text-left w-full max-w-xs">
          <li className="flex items-center gap-2"><span className="text-primary font-bold">✓</span> Multi-channel campaign management</li>
          <li className="flex items-center gap-2"><span className="text-primary font-bold">✓</span> Voice agents with custom scripts</li>
          <li className="flex items-center gap-2"><span className="text-primary font-bold">✓</span> Real-time analytics &amp; reporting</li>
          <li className="flex items-center gap-2"><span className="text-primary font-bold">✓</span> Reusable email sequence templates</li>
        </ul>
      </div>
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
