type AppMode = 'demo' | 'prod'
type AuthMode = 'demo' | 'sms'

const parseBoolean = (value: string | undefined, fallback: boolean): boolean => {
  if (value == null || value.trim() === '') {
    return fallback
  }

  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())
}

export const appMode: AppMode =
  process.env.NEXT_PUBLIC_PCT_APP_MODE === 'demo' ? 'demo' : 'prod'

export const authMode: AuthMode =
  process.env.NEXT_PUBLIC_PCT_AUTH_MODE === 'demo' ? 'demo' : 'sms'

export const showDemoBanner = parseBoolean(
  process.env.NEXT_PUBLIC_PCT_SHOW_DEMO_BANNER,
  appMode === 'demo' || authMode === 'demo',
)

export const enableSampleTasks = parseBoolean(
  process.env.NEXT_PUBLIC_PCT_ENABLE_SAMPLE_TASKS,
  false,
)

export const allowUserUpload = parseBoolean(
  process.env.NEXT_PUBLIC_PCT_ALLOW_USER_UPLOAD,
  true,
)

export const isDemoExperience = appMode === 'demo' || authMode === 'demo' || showDemoBanner
