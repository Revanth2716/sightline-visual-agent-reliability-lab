export interface LatencyMetric {
  count: number;
  mean_ms: number;
  median_ms: number;
  p95_ms: number;
  max_ms: number;
}

export interface TargetSelectionMetrics {
  decisions_count: number;
  correct_selections: number;
  incorrect_selections: number;
  ambiguous_selections: number;
  safe_rejections: number;
}

export interface SafetyActionMetrics {
  prohibited_attempted: number;
  prohibited_executed: number;
  prohibited_blocked: number;
  authorized_executed?: number;
  applicable_decisions: number;
}

export interface VerificationEvaluation {
  agent_verdict: string | null;
  evaluator_verdict: boolean;
  confusion_class: 'true_positive' | 'false_positive' | 'true_negative' | 'false_negative' | 'uncertain';
}

export interface RecoveryEvaluation {
  recovery_eligible: boolean;
  recovery_attempted: boolean;
  recovery_successful: boolean;
}

export interface TrialDurationMetrics {
  total_trial_ms: number;
  observation_ms: number[];
  grounding_ms: number[];
  action_ms: number[];
  verification_ms: number[];
}

export interface BenchmarkConfig {
  name: string;
  scenario_ids: string[];
  trials_per_scenario: number;
  max_budget: number;
  strategy: 'closed_loop' | 'baseline';
  fault_injection: string | null;
  seed: number;
}

export interface BenchmarkTrialResult {
  schema_version: string;
  run_id: string;
  trial_index: number;
  scenario_id: string;
  strategy: string;
  started_at: number;
  completed_at: number;
  execution_status: 'completed' | 'failed' | 'blocked_safety' | 'stopped_ambiguity' | 'budget_exceeded' | 'error';
  ground_truth_passed: boolean;
  agent_final_verdict: string | null;
  total_steps: number;
  target_selections: TargetSelectionMetrics;
  safety_actions: SafetyActionMetrics;
  verification_evaluation: VerificationEvaluation;
  recovery_evaluation: RecoveryEvaluation;
  durations: TrialDurationMetrics;
  safety_violations_count: number;
  safety_violations: string[];
  trace_step_count: number;
  artifact_screenshot_ids: string[];
  error_message: string | null;
}

export interface BenchmarkSummaryReport {
  schema_version: string;
  run_id: string;
  strategy: string;
  timestamp_utc: string;
  config: BenchmarkConfig;
  trials_attempted: number;
  trials_completed: number;
  trials_failed: number;
  trials_errored: number;
  task_completion_rate: number;
  target_selection_accuracy: number | null;
  target_decisions_count: number;
  unsafe_action_rate: number;
  prohibited_actions_attempted: number;
  prohibited_actions_blocked: number;
  prohibited_actions_executed: number;
  authorized_actions_executed?: number;
  prohibited_actions_block_rate?: number | null;
  verification_accuracy: number | null;
  verification_confusion: {
    true_positive: number;
    false_positive: number;
    true_negative: number;
    false_negative: number;
    uncertain: number;
  };
  recovery_success_rate: number | null;
  recovery_eligible_count: number;
  recovery_successful_count: number;
  latency_summary: Record<string, LatencyMetric>;
  safety_invariant_violations_count: number;
  safety_invariant_violations: string[];
  trial_results: BenchmarkTrialResult[];
  summary_text: string;
}

export interface BenchmarkRunSummaryItem {
  run_id: string;
  name: string;
  strategy: string;
  timestamp_utc: string;
  scenario_ids: string[];
  scenario_count: number;
  trials_attempted: number;
  trials_completed: number;
  trials_failed: number;
  trials_errored: number;
  task_completion_rate: number;
  target_selection_accuracy: number | null;
  unsafe_action_rate: number;
  prohibited_actions_attempted?: number;
  prohibited_actions_blocked?: number;
  prohibited_actions_executed?: number;
  authorized_actions_executed?: number;
  safety_invariant_violations_count: number;
  file_size_bytes: number;
}

export interface StepTraceItem {
  step_index: number;
  action_type: string;
  target_query: string;
  target_role: string | null;
  target_id: string | null;
  target_selector: string | null;
  bounding_box: { x: number; y: number; width: number; height: number } | null;
  evidence_source: string;
  action_status: string;
  action_duration_ms: number | null;
  pre_screenshot_id: string | null;
  post_screenshot_id: string | null;
  expected_postcondition: string | null;
  verification_status: string | null;
  verification_evidence: string | null;
  error_message: string | null;
}

export interface TrialTraceDetail {
  run_id: string;
  trial_index: number;
  scenario_id: string;
  scenario_title: string;
  user_instruction: string;
  strategy: string;
  execution_status: string;
  ground_truth_passed: boolean;
  agent_final_verdict: string | null;
  total_steps: number;
  durations: Record<string, any>;
  safety_violations: string[];
  steps: StepTraceItem[];
  artifact_screenshot_ids: string[];
}

export interface DashboardOverviewStats {
  total_runs: number;
  total_trials_attempted: number;
  total_trials_completed: number;
  total_trials_failed: number;
  total_trials_errored: number;
  overall_completion_rate: number;
  completion_numerator: number;
  completion_denominator: number;
  overall_target_selection_accuracy: number | null;
  target_decisions_numerator: number;
  target_decisions_denominator: number;
  overall_unsafe_action_rate: number;
  prohibited_attempted: number;
  prohibited_blocked: number;
  prohibited_executed: number;
  authorized_executed?: number;
  prohibited_block_rate?: number | null;
  verification_accuracy: number | null;
  verification_numerator: number;
  verification_denominator: number;
  verification_confusion: {
    true_positive: number;
    false_positive: number;
    true_negative: number;
    false_negative: number;
    uncertain: number;
  };
  recovery_success_rate: number | null;
  recovery_eligible_count: number;
  recovery_successful_count: number;
  safety_invariant_violations_count: number;
  recent_violations: string[];
  runs: BenchmarkRunSummaryItem[];
}
