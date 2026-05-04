export interface AppConfig {
  remote_provider: string
  remote_provider_label: string
  remote_profiles: Record<string, RemoteProfile>
  webdav_host: string
  webdav_user: string
  webdav_pass: string
  remote_cookie: string
  scan_max_depth: number
  saved_mount_dirs: string[]
  local_scan_max_depth: number
  local_mount_dirs: string[]
  potplayer_path: string
  vlc_path: string
  default_player: string
  video_formats: string[]
  enable_auto_scrape: boolean
  scrape_source: string
  tmdb_api_key: string
  tmdb_api_base: string
  tmdb_web_base: string
  tmdb_image_base: string
  interface_theme: string
  ui_theme: string
  available_themes: string[]
  interface_language: string
  has_basic_config: boolean
  has_local_config: boolean
  has_any_library: boolean
  openlist_enabled: boolean
  openlist_port: number
  openlist_admin_password: string
  openlist_auto_start: boolean
  openlist_binary_version: string
}

export interface RemoteProfile {
  webdav_host: string
  webdav_user: string
  webdav_pass: string
  remote_cookie: string
  saved_mount_dirs: string[]
}

export interface DirectoryItem {
  name: string
  full_path: string
}

export interface JobStatus {
  job_id: string
  name: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  current: number
  total: number
  message: string
  error: string
  result: unknown
}
