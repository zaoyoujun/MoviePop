export interface OpenListStatus {
  running: boolean
  pid: number | null
  port: number
  uptime: string
}

export interface OpenListConfig {
  enabled: boolean
  port: number
  admin_password: string
  auto_start: boolean
  binary_version: string
}

export interface OpenListStorage {
  id: number
  mount_path: string
  driver: string
  addition: Record<string, unknown>
  order: number
  cache_expiration: number
  status: string
  enabled: boolean
}

export interface OpenListDriver {
  name: string
  label: string
  config_fields: OpenListDriverField[]
}

export interface OpenListDriverField {
  name: string
  label: string
  type: string
  required: boolean
  default: unknown
  options?: string[]
}
