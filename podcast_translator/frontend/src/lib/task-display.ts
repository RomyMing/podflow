const LANGUAGE_LABELS: Record<string, string> = {
  zh: '中文',
  'zh-CN': '中文',
  en: '英文',
  ja: '日文',
  ko: '韩文',
  fr: '法文',
  de: '德文',
  es: '西班牙文',
}

const TECHNICAL_CODE_LABELS: Record<string, string> = {
  provider_paused: '外部服务已暂停',
  provider_credentials_missing: '服务令牌或接口密钥未配置',
  provider_invalid_api_key: '接口密钥无效',
  provider_billing_required: '服务余额不足',
  provider_unavailable: '外部服务暂不可用',
  credential_decryption_failed: '接口密钥解密失败',
  storage_unavailable: '对象存储不可用',
  Arrearage: '服务余额不足',
  InvalidApiKey: '接口密钥无效',
  InvalidParameter: '请求参数无效',
  Forbidden: '没有调用权限',
  TimeoutError: '请求超时',
}

const ERROR_MESSAGE_RULES: Array<[RegExp, string]> = [
  [/dashscope api key is not configured/i, 'DashScope 接口密钥未配置。请先在个人设置的 API 管理中添加。'],
  [/hugging face token is not configured/i, 'Hugging Face 令牌未配置。请先配置说话人识别所需的访问令牌。'],
  [/api key is not configured/i, '接口密钥未配置。请先在个人设置的 API 管理中添加。'],
  [/invalid api key|InvalidApiKey/i, '接口密钥无效，请检查后重新保存。'],
  [/arrearage/i, '外部服务余额不足或存在欠费，请处理后继续生成。'],
  [/forbidden/i, '当前接口密钥没有调用权限，请检查服务权限。'],
  [/object storage is unavailable|storage_unavailable/i, '对象存储暂不可用，请稍后重试。'],
  [/pipeline runtime dependency is missing/i, '运行环境缺少必要依赖，请检查服务部署。'],
  [/voice enrollment failed/i, '声音克隆注册失败，系统将尝试使用预设音色。'],
  [/tts synthesis failed|cosyvoice/i, '语音合成失败，请检查语音服务配置后重试。'],
  [/translation failed/i, '文本翻译失败，请检查翻译服务配置后重试。'],
  [/timed out|timeout/i, '外部服务请求超时，请稍后重试。'],
  [/fatal system halt during pipeline traversal/i, '任务处理过程中出现系统异常，请查看后台日志获取详细原因。'],
  [/no refresh token available/i, '登录状态已过期，请重新登录。'],
]

function hasEnglishText(value: string): boolean {
  return /[A-Za-z]{3,}/.test(value)
}

export function formatTaskLanguage(language: string | null | undefined): string {
  if (!language) {
    return '未知语言'
  }
  return LANGUAGE_LABELS[language] || '未知语言'
}

export function formatTaskTechnicalCode(code: string | null | undefined): string | null {
  if (!code) {
    return null
  }

  if (TECHNICAL_CODE_LABELS[code]) {
    return TECHNICAL_CODE_LABELS[code]
  }

  if (code.startsWith('missing_')) {
    return `缺少运行依赖：${code.replace('missing_', '')}`
  }

  return hasEnglishText(code) ? '未识别错误代码' : code
}

export function formatTaskErrorMessage(message: string | null | undefined): string | null {
  if (!message) {
    return null
  }

  const normalized = message.trim()
  for (const [pattern, label] of ERROR_MESSAGE_RULES) {
    if (pattern.test(normalized)) {
      return label
    }
  }

  return hasEnglishText(normalized)
    ? '任务处理过程中出现异常，请查看后台日志获取详细原因。'
    : normalized
}
