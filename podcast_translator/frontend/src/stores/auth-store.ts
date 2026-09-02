import { create } from 'zustand'
import { UserResponse } from '@/types/api'
import { UserService } from '@/services/user-service'
import { AuthService } from '@/services/auth-service'
import { isAuthenticated as checkAuthenticated } from '@/lib/auth'

interface AuthState {
  isAuthenticated: boolean
  user: UserResponse | null
  isLoading: boolean
  error: string | null

  // actions
  checkAuth: () => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  user: null,
  isLoading: true,
  error: null,

  checkAuth: async () => {
    set({ isLoading: true, error: null })
    if (!checkAuthenticated()) {
      set({ isAuthenticated: false, user: null, isLoading: false })
      return
    }

    try {
      const user = await UserService.getMe()
      set({ isAuthenticated: true, user, isLoading: false })
    } catch (err: unknown) {
      const e = err as Error
      console.error('Failed to get user profile', e)
      set({ isAuthenticated: false, user: null, isLoading: false, error: e.message || 'Failed to authenticate' })
    }
  },

  logout: () => {
    AuthService.logout()
    set({ isAuthenticated: false, user: null })
  }
}))
