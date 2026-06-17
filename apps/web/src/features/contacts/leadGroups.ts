export type LeadGroupField =
  | "company"
  | "industry"
  | "title"
  | "product_interest"
  | "source"
  | "phone"

export type LeadGroupOperator = "contains" | "exists"

export type LeadGroupCriterion = {
  field: LeadGroupField
  operator: LeadGroupOperator
  value?: string
}

export type LeadGroup = {
  id: string
  name: string
  description: string
  criteria: LeadGroupCriterion[]
}

export type LeadGroupContact = {
  id: string
  email: string
  company: string | null
  phone: string | null
  industry?: string | null
  title?: string | null
  product_interest?: string | null
  source?: string | null
}

export const leadGroups: LeadGroup[] = [
  {
    id: "financial-services-leaders",
    name: "Financial Services leaders",
    description: "Leads in financial services with leadership or operations roles.",
    criteria: [
      { field: "industry", operator: "contains", value: "Financial Services" },
      { field: "title", operator: "contains", value: "VP" },
    ],
  },
  {
    id: "voice-ready-leads",
    name: "Voice-ready leads",
    description: "Contacts with phone numbers available for voice outreach.",
    criteria: [{ field: "phone", operator: "exists" }],
  },
  {
    id: "messaging-hub-leads",
    name: "Messaging Hub leads",
    description: "Contacts sourced from Messaging Hub conversations.",
    criteria: [{ field: "source", operator: "contains", value: "Messaging Hub" }],
  },
]

export function criterionLabel(criterion: LeadGroupCriterion) {
  if (criterion.operator === "exists") {
    return `${criterion.field.replace(/_/g, " ")} exists`
  }
  return `${criterion.field.replace(/_/g, " ")} contains ${criterion.value}`
}

export function matchesLeadGroup(contact: LeadGroupContact, group: LeadGroup) {
  return group.criteria.every((criterion) => {
    const rawValue = contact[criterion.field]
    if (criterion.operator === "exists") {
      return Boolean(String(rawValue || "").trim())
    }
    return String(rawValue || "")
      .toLowerCase()
      .includes(String(criterion.value || "").toLowerCase())
  })
}
