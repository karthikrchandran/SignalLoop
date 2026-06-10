import { Link } from "@tanstack/react-router"
import {
  ArrowLeft,
  Bot,
  Clock3,
  Link2Off,
  Loader2,
  Mail,
  Pencil,
  PhoneCall,
  RefreshCw,
  Target,
  UserPlus,
  Users,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import AccountFormDialog from "./AccountFormDialog"
import AssignContactsDialog from "./AssignContactsDialog"
import {
  type AccountWriteInput,
  assignContactsToAccount,
  type Customer360AccountProfile,
  type Customer360ChannelSummary,
  type Customer360Contact,
  type Customer360OpenWork,
  type Customer360TimelineEvent,
  getCustomer360AccountProfile,
  unassignContactFromAccount,
  updateAccount,
} from "./api"

type Customer360AccountProfilePageProps = {
  accountId: string
}

const channelDefaults: Customer360ChannelSummary[] = [
  {
    channel: "chatbot",
    label: "Chatbot",
    count: 0,
    status: "",
    detail: "No activity yet.",
  },
  {
    channel: "email",
    label: "Email",
    count: 0,
    status: "",
    detail: "No activity yet.",
  },
  {
    channel: "voice",
    label: "Voice",
    count: 0,
    status: "",
    detail: "No activity yet.",
  },
  {
    channel: "prospecting",
    label: "Prospecting",
    count: 0,
    status: "",
    detail: "No activity yet.",
  },
]

function pluralizeContacts(count: number) {
  return `${count} contact${count === 1 ? "" : "s"}`
}

function formatStatus(value?: string | null) {
  if (!value) return "-"

  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatDate(value?: string | null) {
  if (!value) return "-"

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"

  return date.toLocaleString()
}

function errorMessage(error: unknown, fallback = "Could not load account") {
  return error instanceof Error ? error.message : fallback
}

function contactName(contact: Customer360Contact) {
  const name = contact.display_name?.trim()
  if (name) return name

  const fallbackName = [contact.first_name, contact.last_name]
    .filter(Boolean)
    .join(" ")
    .trim()

  return fallbackName || contact.email
}

function channelSummaries(profile: Customer360AccountProfile) {
  return channelDefaults.map((fallback) => {
    const summary = profile.channel_summaries[fallback.channel]

    return summary
      ? {
          ...summary,
          label: summary.label || fallback.label,
          detail: summary.detail || fallback.detail,
        }
      : fallback
  })
}

function ChannelIcon({ channel }: { channel: string }) {
  if (channel === "chatbot") return <Bot className="size-4" />
  if (channel === "email") return <Mail className="size-4" />
  if (channel === "voice") return <PhoneCall className="size-4" />
  return <Target className="size-4" />
}

export default function Customer360AccountProfilePage({
  accountId,
}: Customer360AccountProfilePageProps) {
  const [profile, setProfile] = useState<Customer360AccountProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState("")
  const [refreshError, setRefreshError] = useState("")
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [assignDialogOpen, setAssignDialogOpen] = useState(false)
  const [mutationError, setMutationError] = useState("")
  const [unlinkingContactId, setUnlinkingContactId] = useState("")
  const latestRequestId = useRef(0)
  const profileRef = useRef<Customer360AccountProfile | null>(null)

  const loadProfile = useCallback(async () => {
    const requestId = latestRequestId.current + 1
    latestRequestId.current = requestId
    const hasStaleProfile = Boolean(profileRef.current)

    if (hasStaleProfile) {
      setRefreshing(true)
      setRefreshError("")
    } else {
      setLoading(true)
      setLoadError("")
    }

    try {
      const nextProfile = await getCustomer360AccountProfile(accountId)
      if (latestRequestId.current !== requestId) return

      profileRef.current = nextProfile
      setProfile(nextProfile)
      setLoadError("")
      setRefreshError("")
    } catch (requestError) {
      if (latestRequestId.current !== requestId) return

      if (profileRef.current) {
        setRefreshError(errorMessage(requestError))
      } else {
        setLoadError(errorMessage(requestError))
      }
    } finally {
      if (latestRequestId.current === requestId) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [accountId])

  useEffect(() => {
    profileRef.current = null
    setProfile(null)
    setLoadError("")
    setRefreshError("")
    setMutationError("")
    setLoading(true)
    setRefreshing(false)
    void loadProfile()
  }, [loadProfile])

  const account = profile?.account
  const accountName = account?.name || "Customer 360 account"
  const contactCount = profile?.contacts.length ?? 0
  const handleUpdateAccount = async (input: AccountWriteInput) => {
    await updateAccount(accountId, input)
    await loadProfile()
  }

  const handleAssignContacts = async (contactIds: string[]) => {
    setMutationError("")
    await assignContactsToAccount(accountId, contactIds)
    await loadProfile()
  }

  const handleUnassignContact = async (contact: Customer360Contact) => {
    setUnlinkingContactId(contact.id)
    setMutationError("")
    try {
      await unassignContactFromAccount(accountId, contact.id)
      await loadProfile()
    } catch (unlinkError) {
      setMutationError(errorMessage(unlinkError, "Could not unlink contact"))
    } finally {
      setUnlinkingContactId("")
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <Button asChild variant="ghost" size="sm" className="w-fit">
          <Link to="/customer-360">
            <ArrowLeft className="size-4" />
            Accounts
          </Link>
        </Button>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">
              Customer 360 account
            </p>
            <h1 className="mt-1 break-words text-3xl font-semibold tracking-tight">
              {accountName}
            </h1>
            {account ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {account.industry && (
                  <Badge variant="outline" className="max-w-full truncate">
                    {account.industry}
                  </Badge>
                )}
                <Badge variant="secondary">
                  {formatStatus(account.status)}
                </Badge>
                <Badge variant="outline">
                  {pluralizeContacts(contactCount)}
                </Badge>
                {account.tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="outline"
                    className="max-w-full truncate"
                  >
                    {tag}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Loading account context.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => setEditDialogOpen(true)}
              disabled={!account}
            >
              <Pencil className="size-4" />
              Edit account
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => void loadProfile()}
              disabled={loading || refreshing}
            >
              {loading || refreshing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {!profile && loading ? (
        <Card>
          <CardContent className="flex min-h-40 items-center justify-center text-muted-foreground">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="size-4 animate-spin" />
              Loading account profile...
            </span>
          </CardContent>
        </Card>
      ) : null}

      {!profile && loadError ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load account profile</AlertTitle>
          <AlertDescription>
            <p>{loadError}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void loadProfile()}
            >
              <RefreshCw className="size-4" />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {profile ? (
        <>
          {refreshError ? (
            <Alert variant="destructive">
              <AlertTitle>Refresh failed</AlertTitle>
              <AlertDescription>
                Showing the last loaded profile. {refreshError}
              </AlertDescription>
            </Alert>
          ) : null}

          {mutationError ? (
            <Alert variant="destructive">
              <AlertTitle>Contact update failed</AlertTitle>
              <AlertDescription>{mutationError}</AlertDescription>
            </Alert>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Account summary</CardTitle>
              <CardDescription>
                Shared account context for every engagement channel.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="break-words text-sm leading-6">
                {profile.account.summary || "No account summary available."}
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {channelSummaries(profile).map((summary) => (
              <Card key={summary.channel}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <ChannelIcon channel={summary.channel} />
                      {summary.label}
                    </CardTitle>
                    <Badge variant="secondary">{summary.count}</Badge>
                  </div>
                  {summary.status ? (
                    <CardDescription>
                      {formatStatus(summary.status)}
                    </CardDescription>
                  ) : null}
                </CardHeader>
                <CardContent>
                  <p className="break-words text-sm text-muted-foreground">
                    {summary.detail || "No activity yet."}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <ContactsPanel
              contacts={profile.contacts}
              unlinkingContactId={unlinkingContactId}
              onAssignClick={() => setAssignDialogOpen(true)}
              onUnassign={(contact) => void handleUnassignContact(contact)}
            />
            <NextBestActionPanel profile={profile} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ProspectingBriefPanel profile={profile} />
            <OpenWorkPanel openWork={profile.open_work} />
          </div>

          <TimelinePanel timeline={profile.timeline} />
        </>
      ) : null}

      <AccountFormDialog
        open={editDialogOpen}
        mode="edit"
        account={account}
        onOpenChange={setEditDialogOpen}
        onSubmit={handleUpdateAccount}
      />
      <AssignContactsDialog
        open={assignDialogOpen}
        existingContactIds={
          profile?.contacts.map((contact) => contact.id) ?? []
        }
        onOpenChange={setAssignDialogOpen}
        onAssign={handleAssignContacts}
      />
    </div>
  )
}

function ContactsPanel({
  contacts,
  unlinkingContactId,
  onAssignClick,
  onUnassign,
}: {
  contacts: Customer360Contact[]
  unlinkingContactId: string
  onAssignClick: () => void
  onUnassign: (contact: Customer360Contact) => void
}) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <Users className="size-4" />
            Contacts
          </CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAssignClick}
          >
            <UserPlus className="size-4" />
            Assign contacts
          </Button>
        </div>
        <CardDescription>
          {pluralizeContacts(contacts.length)} linked to this account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {contacts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No contacts linked to this account yet.
          </p>
        ) : (
          <div className="divide-y">
            {contacts.map((contact) => (
              <div
                key={contact.id}
                className="grid gap-2 py-3 first:pt-0 last:pb-0 md:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0">
                  <p className="break-words font-medium">
                    {contactName(contact)}
                  </p>
                  <p className="break-words text-sm text-muted-foreground">
                    {contact.email}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2 md:justify-end">
                  {contact.phone ? (
                    <Badge variant="outline" className="max-w-full truncate">
                      {contact.phone}
                    </Badge>
                  ) : null}
                  <Badge variant="secondary" className="max-w-full truncate">
                    {contact.timezone || "-"}
                  </Badge>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Unlink ${contactName(contact)}`}
                        onClick={() => onUnassign(contact)}
                        disabled={Boolean(unlinkingContactId)}
                      >
                        {unlinkingContactId === contact.id ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Link2Off className="size-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Unlink contact</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function NextBestActionPanel({
  profile,
}: {
  profile: Customer360AccountProfile
}) {
  const action = profile.next_best_action

  return (
    <Card>
      <CardHeader>
        <CardTitle>Next best action</CardTitle>
        <CardDescription>Highest-priority account movement.</CardDescription>
      </CardHeader>
      <CardContent>
        {action ? (
          <div className="space-y-3">
            <p className="break-words font-medium">{action.title}</p>
            <p className="break-words text-sm text-muted-foreground">
              {action.reason}
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{formatStatus(action.source)}</Badge>
              <Badge variant="secondary">
                {formatStatus(action.priority)} priority
              </Badge>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No next best action queued.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ProspectingBriefPanel({
  profile,
}: {
  profile: Customer360AccountProfile
}) {
  const brief = profile.prospecting_brief

  return (
    <Card>
      <CardHeader>
        <CardTitle>Prospecting brief</CardTitle>
        <CardDescription>Latest account-level sales context.</CardDescription>
      </CardHeader>
      <CardContent>
        {brief ? (
          <div className="space-y-3">
            <p className="break-words text-sm leading-6">
              {brief.account_summary}
            </p>
            <p className="break-words text-sm text-muted-foreground">
              {brief.suggested_next_action || "No suggested action available."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge
                variant={brief.email_draft_available ? "secondary" : "outline"}
              >
                Email draft {brief.email_draft_available ? "ready" : "missing"}
              </Badge>
              <Badge
                variant={brief.voice_opener_available ? "secondary" : "outline"}
              >
                Voice opener{" "}
                {brief.voice_opener_available ? "ready" : "missing"}
              </Badge>
              <Badge variant="outline">{formatDate(brief.created_at)}</Badge>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No prospecting brief yet.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function OpenWorkPanel({ openWork }: { openWork: Customer360OpenWork[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Open work</CardTitle>
        <CardDescription>
          Unresolved account tasks and escalations.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {openWork.length === 0 ? (
          <p className="text-sm text-muted-foreground">No open work queued.</p>
        ) : (
          <div className="divide-y">
            {openWork.map((item) => (
              <div
                key={item.id}
                className="space-y-2 py-3 first:pt-0 last:pb-0"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="break-words font-medium">{item.title}</p>
                  <Badge variant="secondary">{formatStatus(item.status)}</Badge>
                </div>
                <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
                  <span>{formatStatus(item.source)}</span>
                  <span>{item.contact_name || "Account-level"}</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function TimelinePanel({ timeline }: { timeline: Customer360TimelineEvent[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock3 className="size-4" />
          Unified account timeline
        </CardTitle>
        <CardDescription>
          Account activity merged across chatbot, email, voice, and prospecting.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {timeline.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No timeline events yet.
          </p>
        ) : (
          <div className="divide-y">
            {timeline.map((event) => (
              <div
                key={event.id}
                className="grid gap-2 py-4 first:pt-0 last:pb-0 md:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0 space-y-1">
                  <p className="break-words font-medium">{event.title}</p>
                  <p className="break-words text-sm text-muted-foreground">
                    {event.detail}
                  </p>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{formatStatus(event.source)}</span>
                    <span>{formatStatus(event.event_type)}</span>
                    <span>{event.contact_name || "Account-level"}</span>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground md:text-right">
                  {formatDate(event.timestamp)}
                </p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
