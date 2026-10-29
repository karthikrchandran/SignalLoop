import { Appearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-[linear-gradient(180deg,#1d466c_0%,#163551_52%,#10283f_100%)] text-white lg:flex lg:flex-col lg:justify-between lg:p-12">
        <Logo variant="full" asLink={false} tone="inverse" />
        <div className="max-w-md">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8fd2ff]">
            SignalLoop
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">
            Intelligent Outreach, Simplified
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/75">
            Reach your audience across email and voice channels — with AI-driven
            personalisation, prebuilt sequences, and real-time analytics in one
            platform.
          </p>
        </div>
        <ul className="mt-8 space-y-3 text-sm text-white/80">
          <li className="flex items-center gap-2">
            <span className="text-[#8fd2ff]">✓</span> Multi-channel campaign
            management
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#8fd2ff]">✓</span> Voice agents with custom
            scripts
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#8fd2ff]">✓</span> Real-time analytics &amp;
            reporting
          </li>
          <li className="flex items-center gap-2">
            <span className="text-[#8fd2ff]">✓</span> Reusable email sequence
            templates
          </li>
        </ul>
      </div>
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-end">
          <Appearance />
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-sm rounded-2xl border bg-card p-6 shadow-sm">
            {children}
          </div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
