import { useEffect, useState } from "react"
import { RotateCcw } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { type ChatbotOptOut, listChatbotOptOuts, removeChatbotOptOut } from "@/features/chatbot/api"

export function OptOutsTab() {
  const [rows, setRows] = useState<ChatbotOptOut[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<ChatbotOptOut | null>(null)

  const load = async () => {
    setLoading(true)
    const response = await listChatbotOptOuts()
    setRows(response.data)
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  const confirm = async () => {
    if (!selected) return
    await removeChatbotOptOut(selected.id)
    setSelected(null)
    toast.success("Visitor re-enabled")
    await load()
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading opt-outs...</div>
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">No active messaging opt-outs.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Channel</TableHead>
              <TableHead>Visitor</TableHead>
              <TableHead>Opted Out</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.channel_type.replace("_", " ")}</TableCell>
                <TableCell>{row.visitor_id}</TableCell>
                <TableCell>{new Date(row.created_at).toLocaleString()}</TableCell>
                <TableCell>{row.actor}</TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" onClick={() => setSelected(row)} className="gap-2">
                    <RotateCcw className="size-4" />
                    Re-enable
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Re-enable visitor</DialogTitle>
            <DialogDescription>
              Re-enabling bot engagement requires explicit visitor re-consent. This removes the active opt-out for {selected?.visitor_id}.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>Cancel</Button>
            <Button onClick={confirm}>Confirm re-enable</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
