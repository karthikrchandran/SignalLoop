import { Loader2 } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  type AccountWriteInput,
  type Customer360Account,
} from "./api"

type AccountFormDialogProps = {
  open: boolean
  mode: "create" | "edit"
  account?: Customer360Account | null
  onOpenChange: (open: boolean) => void
  onSubmit: (input: AccountWriteInput) => Promise<void>
}

function parseTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
}

function optionalText(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Could not save account"
}

export default function AccountFormDialog({
  open,
  mode,
  account,
  onOpenChange,
  onSubmit,
}: AccountFormDialogProps) {
  const initialValues = useMemo(
    () => ({
      name: account?.name ?? "",
      website: account?.website_url ?? "",
      industry: account?.industry ?? "",
      status: account?.status ?? "active",
      summary: account?.summary ?? "",
      tags: account?.tags.join(", ") ?? "",
    }),
    [account],
  )
  const [name, setName] = useState(initialValues.name)
  const [website, setWebsite] = useState(initialValues.website)
  const [industry, setIndustry] = useState(initialValues.industry)
  const [status, setStatus] = useState(initialValues.status)
  const [summary, setSummary] = useState(initialValues.summary)
  const [tags, setTags] = useState(initialValues.tags)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!open) return

    setName(initialValues.name)
    setWebsite(initialValues.website)
    setIndustry(initialValues.industry)
    setStatus(initialValues.status)
    setSummary(initialValues.summary)
    setTags(initialValues.tags)
    setError("")
  }, [initialValues, open])

  const submitLabel = mode === "create" ? "Create account" : "Save changes"

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError("Account name is required.")
      return
    }

    setSaving(true)
    setError("")
    try {
      await onSubmit({
        name: trimmedName,
        website_url: optionalText(website),
        industry: optionalText(industry),
        status: status.trim() || "active",
        summary: optionalText(summary),
        tags: parseTags(tags),
      })
      onOpenChange(false)
    } catch (submitError) {
      setError(errorMessage(submitError))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => !saving && onOpenChange(nextOpen)}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {mode === "create" ? "New account" : "Edit account"}
            </DialogTitle>
            <DialogDescription>
              Maintain account metadata used across Customer 360.
            </DialogDescription>
          </DialogHeader>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="account-name">Name</Label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="organization"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-website">Website</Label>
              <Input
                id="account-website"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
                placeholder="https://example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-industry">Industry</Label>
              <Input
                id="account-industry"
                value={industry}
                onChange={(event) => setIndustry(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-status">Status</Label>
              <Input
                id="account-status"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="account-tags">Tags</Label>
              <Input
                id="account-tags"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="priority, healthcare"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="account-summary">Summary</Label>
              <Textarea
                id="account-summary"
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                rows={4}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving || !name.trim()}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : null}
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
