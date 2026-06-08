import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { isChatbotDemoMode } from "@/features/chatbot/demo"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null || isChatbotDemoMode()
}

const demoUser = {
  id: "demo-user",
  email: "demo@engagehub.local",
  full_name: "Demo Admin",
  is_active: true,
  is_superuser: true,
  role: "admin",
} as UserPublic & { role: string }

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const chatbotDemoMode = isChatbotDemoMode()

  const currentUserQuery = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: UsersService.readUserMe,
    enabled: isLoggedIn() && !chatbotDemoMode,
    retry: false,
  })

  useEffect(() => {
    if (!currentUserQuery.isError || !isLoggedIn()) {
      return
    }

    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }, [currentUserQuery.isError, navigate])

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ requestBody: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    const response = await LoginService.loginAccessToken({
      formData: data,
    })
    localStorage.setItem("access_token", response.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user: chatbotDemoMode ? demoUser : currentUserQuery.data,
    isLoading: chatbotDemoMode ? false : currentUserQuery.isLoading,
    isError: chatbotDemoMode ? false : currentUserQuery.isError,
    error: chatbotDemoMode ? null : currentUserQuery.error,
  }
}

export { isLoggedIn }
export default useAuth
