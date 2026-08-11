import { useQuery } from "@tanstack/react-query"

import { getSuiteContext } from "@/lib/signalloop-api"

export const useSuiteContext = () =>
  useQuery({
    queryKey: ["suite-context"],
    queryFn: () => getSuiteContext(),
    retry: false,
  })
