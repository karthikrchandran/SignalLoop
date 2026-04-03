import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type QuietHoursEditorProps = {
  start: string
  end: string
  timezone: string
  disabled?: boolean
  onChange: (value: { start: string; end: string; timezone: string }) => void
}

export function QuietHoursEditor({ start, end, timezone, disabled = false, onChange }: QuietHoursEditorProps) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div>
        <Label htmlFor="quiet-start">Quiet start</Label>
        <Input
          id="quiet-start"
          value={start}
          disabled={disabled}
          onChange={(event) => onChange({ start: event.target.value, end, timezone })}
          placeholder="21:00"
        />
      </div>
      <div>
        <Label htmlFor="quiet-end">Quiet end</Label>
        <Input
          id="quiet-end"
          value={end}
          disabled={disabled}
          onChange={(event) => onChange({ start, end: event.target.value, timezone })}
          placeholder="08:00"
        />
      </div>
      <div>
        <Label htmlFor="quiet-timezone">Timezone</Label>
        <Input
          id="quiet-timezone"
          value={timezone}
          disabled={disabled}
          onChange={(event) => onChange({ start, end, timezone: event.target.value })}
          placeholder="UTC"
        />
      </div>
    </div>
  )
}
