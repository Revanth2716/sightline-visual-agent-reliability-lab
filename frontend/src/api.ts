import {
  BenchmarkRunSummaryItem,
  BenchmarkSummaryReport,
  BenchmarkTrialResult,
  DashboardOverviewStats,
  TrialTraceDetail,
} from './types';

const BASE_URL = '';

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(`${BASE_URL}${url}`);
  if (!resp.ok) {
    let errorDetail = `HTTP ${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body.detail) errorDetail = body.detail;
    } catch {
      // Ignore text parse failure
    }
    throw new Error(errorDetail);
  }
  return resp.json();
}

export async function getOverviewStats(): Promise<DashboardOverviewStats> {
  return fetchJson<DashboardOverviewStats>('/api/dashboard/overview');
}

export async function getRunsList(
  scenarioId?: string,
  strategy?: string
): Promise<BenchmarkRunSummaryItem[]> {
  const params = new URLSearchParams();
  if (scenarioId) params.append('scenario_id', scenarioId);
  if (strategy) params.append('strategy', strategy);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetchJson<BenchmarkRunSummaryItem[]>(`/api/dashboard/runs${query}`);
}

export async function getRunReport(runId: string): Promise<BenchmarkSummaryReport> {
  return fetchJson<BenchmarkSummaryReport>(`/api/dashboard/runs/${encodeURIComponent(runId)}`);
}

export async function getTrialDetail(
  runId: string,
  trialIndex: number
): Promise<BenchmarkTrialResult> {
  return fetchJson<BenchmarkTrialResult>(
    `/api/dashboard/runs/${encodeURIComponent(runId)}/trials/${trialIndex}`
  );
}

export async function getTrialTrace(
  runId: string,
  trialIndex: number
): Promise<TrialTraceDetail> {
  return fetchJson<TrialTraceDetail>(
    `/api/dashboard/runs/${encodeURIComponent(runId)}/trials/${trialIndex}/trace`
  );
}

export function getScreenshotUrl(screenshotId: string): string {
  return `/api/artifacts/screenshots/${encodeURIComponent(screenshotId)}`;
}
