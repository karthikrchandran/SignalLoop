import { useState } from "react"
import { CheckCircle2, Circle, ListOrdered, Plus, Trash2 } from "lucide-react"

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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type StepType = "email" | "wait" | "voice"

interface SequenceStep {
  id: string
  type: StepType
  label: string
  delay?: string
}

interface Sequence {
  id: string
  name: string
  description: string
  status: "Active" | "Draft" | "Paused"
  steps: SequenceStep[]
  enrolledCount: number
}

const PREBUILT_SEQUENCES: Sequence[] = [
  {
    id: "seq-1",
    name: "Welcome Onboarding Series",
    description: "Nurture new contacts through onboarding with 4 timed touchpoints.",
    status: "Active",
    enrolledCount: 1220,
    steps: [
      { id: "s1-1", type: "email", label: "Welcome email", delay: "Immediately" },
      { id: "s1-2", type: "wait", label: "Wait 3 days", delay: "3 days" },
      { id: "s1-3", type: "email", label: "Getting started tips", delay: "Day 3" },
      { id: "s1-4", type: "wait", label: "Wait 4 days", delay: "4 days" },
      { id: "s1-5", type: "email", label: "Success story + CTA", delay: "Day 7" },
    ],
  },
  {
    id: "seq-2",
    name: "Product Launch Sequence",
    description: "Build anticipation and convert interest at launch.",
    status: "Draft",
    enrolledCount: 0,
    steps: [
      { id: "s2-1", type: "email", label: "Teaser announcement", delay: "Immediately" },
      { id: "s2-2", type: "wait", label: "Wait 2 days", delay: "2 days" },
      { id: "s2-3", type: "email", label: "Feature deep-dive", delay: "Day 2" },
      { id: "s2-4", type: "wait", label: "Wait 5 days", delay: "5 days" },
      { id: "s2-5", type: "email", label: "Launch day offer", delay: "Day 7" },
    ],
  },
  {
    id: "seq-3",
    name: "Re-engagement Drip",
    description: "Win back contacts who have gone quiet in the last 90 days.",
    status: "Paused",
    enrolledCount: 780,
    steps: [
      { id: "s3-1", type: "email", label: "We miss you", delay: "Immediately" },
      { id: "s3-2", type: "wait", label: "Wait 7 days", delay: "7 days" },
      { id: "s3-3", type: "email", label: "Exclusive comeback offer", delay: "Day 7" },
      { id: "s3-4", type: "wait", label: "Wait 5 days", delay: "5 days" },
      { id: "s3-5", type: "voice", label: "Morgan follow-up call", delay: "Day 12" },
    ],
  },
]

const STEP_TYPE_COLORS: Record<StepType, string> = {
  email: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  wait: "bg-muted text-muted-foreground",
  voice: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
}

const STATUS_VARIANT: Record<Sequence["status"], "default" | "secondary" | "outline"> = {
  Active: "default",
  Draft: "outline",
  Paused: "secondary",
}

export default function SequencesPage() {
  const [sequences, setSequences] = useState<Sequence[]>(PREBUILT_SEQUENCES)
  const [newName, setNewName] = useState("")
  const [newDesc, setNewDesc] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)

  const handleCreate = () => {
    if (!newName.trim()) return
    const seq: Sequence = {
      id: `seq-${Date.now()}`,
      name: newName.trim(),
      description: newDesc.trim() || "Custom sequence",
      status: "Draft",
      enrolledCount: 0,
      steps: [
        { id: `step-${Date.now()}`, type: "email", label: "First email", delay: "Immediately" },
      ],
    }
    setSequences((prev) => [...prev, seq])
    setNewName("")
    setNewDesc("")
    setDialogOpen(false)
  }

  const handleDelete = (id: string) => {
    setSequences((prev) => prev.filter((s) => s.id !== id))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
            <ListOrdered className="h-7 w-7 text-primary" />
            Sequences
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Automate multi-step outreach flows combining emails and voice
            touchpoints.
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              New Sequence
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Sequence</DialogTitle>
              <DialogDescription>
                Give your sequence a name and optional description to get
                started.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="space-y-1">
                <Label>Name</Label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Spring Promotion Series"
                />
              </div>
              <div className="space-y-1">
                <Label>Description</Label>
                <Input
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Optional short description"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={!newName.trim()}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sequences.map((seq) => (
          <Card key={seq.id} className="border-border/70 flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base">{seq.name}</CardTitle>
                <Badge variant={STATUS_VARIANT[seq.status]}>{seq.status}</Badge>
              </div>
              <CardDescription>{seq.description}</CardDescription>
              {seq.enrolledCount > 0 && (
                <p className="text-xs text-muted-foreground">
                  {seq.enrolledCount.toLocaleString()} contacts enrolled
                </p>
              )}
            </CardHeader>
            <CardContent className="flex-1 space-y-2">
              <ol className="space-y-1.5">
                {seq.steps.map((step) => (
                  <li key={step.id} className="flex items-center gap-2 text-sm">
                    {step.type === "wait" ? (
                      <Circle className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5 text-primary shrink-0" />
                    )}
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${STEP_TYPE_COLORS[step.type]}`}>
                      {step.type}
                    </span>
                    <span className="text-muted-foreground truncate">{step.label}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
            <div className="px-6 pb-5 flex gap-2">
              <Button size="sm" variant="outline" className="flex-1">
                Edit
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-rose-500 hover:text-rose-600"
                onClick={() => handleDelete(seq.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
