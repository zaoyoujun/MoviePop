import api from './index'
import type { ReportData } from '../types/report'

export async function fetchReport(): Promise<ReportData> {
  const { data } = await api.get('/api/report')
  return data
}
