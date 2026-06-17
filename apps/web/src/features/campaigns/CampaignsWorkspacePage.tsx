import { useEffect, useState } from "react"
import { Loader2, RefreshCw } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import CampaignIntakeWizardPage from "@/features/campaigns/CampaignIntakeWizardPage"
import { signalloopRequest } from "@/lib/signalloop-api"

type CampaignPublic = {
  id: string
  name: string
  status: string
}

type CampaignsResponse = {
  data: CampaignPublic[]
  count: number
}

export default function CampaignsWorkspacePage() {
  const [campaigns, setCampaigns] = useState<CampaignPublic[]>([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState("")

  async function loadCampaigns() {
    setLoading(true)
    setFeedback("")
    try {
      const response = await signalloopRequest<CampaignsResponse>("/api/v1/campaigns/")
      setCampaigns(response.data)
      setCount(response.count)
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Could not load campaigns")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCampaigns()
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Campaigns</h1>
          <p className="text-sm text-muted-foreground">
            Review campaign drafts first, then create a new campaign when needed.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadCampaigns()} disabled={loading}>
          {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Refresh
        </Button>
      </div>

      {feedback && (
        <Alert>
          <p className="text-sm">{feedback}</p>
        </Alert>
      )}

      <Tabs defaultValue="list" className="gap-4">
        <TabsList className="flex h-auto w-fit flex-wrap">
          <TabsTrigger value="list">Campaign List</TabsTrigger>
          <TabsTrigger value="create">Create Campaign</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <Card>
            <CardHeader>
              <CardTitle>Campaign List</CardTitle>
              <CardDescription>{count} campaign{count === 1 ? "" : "s"} in this workspace.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={2} className="py-10 text-center text-muted-foreground">
                        No campaigns found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    campaigns.map((campaign) => (
                      <TableRow key={campaign.id}>
                        <TableCell className="font-medium">{campaign.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{campaign.status}</Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="create">
          <CampaignIntakeWizardPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
