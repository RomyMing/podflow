export const setTokens = (accessToken: string, refreshToken: string) => {
  if (typeof window === 'undefined') return
  localStorage.setItem('access_token', accessToken)
  localStorage.setItem('refresh_token', refreshToken)
}

export const getAccessToken = () => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('access_token')
}

export const getRefreshToken = () => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('refresh_token')
}

export const clearTokens = () => {
  if (typeof window === 'undefined') return
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export const isAuthenticated = () => {
  return !!getAccessToken()
}
