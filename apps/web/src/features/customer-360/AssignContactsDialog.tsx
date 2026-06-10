import { Loader2, Search } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import { type AssignableContact, listContacts } from "./api"

type AssignContactsDialogProps = {
  open: boolean
  existingContactIds: string[]
  onOpenChange: (open: boolean) => void
  onAssign: (contactIds: string[]) => Promise<void>
}

function contactName(contact: AssignableContact) {
  const displayName = contact.display_name?.trim()
  if (displayName) return displayName

  const fallbackName = [contact.first_name, contact.last_name]
    .filter(Boolean)
    .join(" ")
    .trim()

  return fallbackName || contact.email
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Could not assign contacts"
}

export default function AssignContactsDialog({
  open,
  existingContactIds,
  onOpenChange,
  onAssign,
}: AssignContactsDialogProps) {
  const [search, setSearch] = useState("")
  const [contacts, setContacts] = useState<AssignableContact[]>([])
  const [selectedContactIds, setSelectedContactIds] = useState<Set<string>>(
    () => new Set(),
  )
  const [loading, setLoading] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [error, setError] = useState("")
  const [hasSearched, setHasSearched] = useState(false)

  const existingContactIdSet = useMemo(
    () => new Set(existingContactIds),
    [existingContactIds],
  )
  const availableContacts = useMemo(
    () =>
      contacts.filter(
        (contact) => !contact.account_id && !existingContactIdSet.has(contact.id),
      ),
    [contacts, existingContactIdSet],
  )

  useEffect(() => {
    if (!open) return

    setSearch("")
    setContacts([])
    setSelectedContactIds(new Set())
    setError("")
    setHasSearched(false)
  }, [open])

  const selectedCount = selectedContactIds.size

  const runSearch = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    setLoading(true)
    setError("")
    setSelectedContactIds(new Set())

    try {
      const response = await listContacts(search)
      setContacts(response.data)
      setHasSearched(true)
    } catch (searchError) {
      setError(errorMessage(searchError))
    } finally {
      setLoading(false)
    }
  }

  const toggleContact = (contactId: string, checked: boolean) => {
    setSelectedContactIds((previous) => {
      const next = new Set(previous)
      if (checked) {
        next.add(contactId)
      } else {
        next.delete(contactId)
      }
      return next
    })
  }

  const handleAssign = async () => {
    if (selectedContactIds.size === 0) return

    setAssigning(true)
    setError("")
    try {
      await onAssign(Array.from(selectedContactIds))
      onOpenChange(false)
    } catch (assignError) {
      setError(errorMessage(assignError))
    } finally {
      setAssigning(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => !assigning && onOpenChange(nextOpen)}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Assign contacts</DialogTitle>
          <DialogDescription>
            Search the contact pool and link selected contacts to this account.
          </DialogDescription>
        </DialogHeader>

        <form className="flex flex-wrap gap-2" onSubmit={runSearch}>
          <div className="relative min-w-64 flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Search contacts"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-9"
              placeholder="Search contacts"
            />
          </div>
          <Button type="submit" variant="outline" disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : null}
            Search contacts
          </Button>
        </form>

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="rounded-md border">
          {loading ? (
            <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 size-4 animate-spin" />
              Loading contacts...
            </div>
          ) : !hasSearched ? (
            <p className="p-4 text-sm text-muted-foreground">
              Search contacts to find people available for this account.
            </p>
          ) : availableContacts.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              No available contacts found.
            </p>
          ) : (
            <div className="divide-y">
              {availableContacts.map((contact) => {
                const name = contactName(contact)
                const checkboxId = `assign-contact-${contact.id}`
                const checked = selectedContactIds.has(contact.id)

                return (
                  <div
                    key={contact.id}
                    className="grid gap-3 p-3 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center"
                  >
                    <Checkbox
                      id={checkboxId}
                      aria-label={`Select ${name}`}
                      checked={checked}
                      onCheckedChange={(nextChecked) =>
                        toggleContact(contact.id, nextChecked === true)
                      }
                    />
                    <Label
                      htmlFor={checkboxId}
                      className="min-w-0 cursor-pointer flex-col items-start gap-1"
                    >
                      <span className="break-words font-medium">{name}</span>
                      <span className="break-words text-sm font-normal text-muted-foreground">
                        {contact.email}
                      </span>
                    </Label>
                    <span className="text-sm text-muted-foreground">
                      {contact.company || "No company"}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <DialogFooter className="items-center gap-3 sm:justify-between">
          <p className="text-sm text-muted-foreground">
            {selectedCount} selected
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={assigning}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleAssign()}
              disabled={assigning || selectedCount === 0}
            >
              {assigning ? <Loader2 className="size-4 animate-spin" /> : null}
              Assign selected
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
