export interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: 'admin' | 'analyst' | 'viewer'
  is_active: boolean
}

export interface RuleHit {
  rule_id: number
  rule_name: string
  rule_type: string
  severity: number
  detail: string
}

export interface RiskFactors {
  components: { name: string; raw_value: number; weight: number; contribution: number }[]
  rule_hits: RuleHit[]
  model_signals: {
    supervised_fraud_probability: number | null
    anomaly_score: number | null
  }
  behavioral_context: Record<string, number | boolean>
}

export interface Transaction {
  id: number
  transaction_id: string
  customer_id: string
  timestamp: string
  amount: number
  currency: string
  merchant: string
  location: string
  channel: string
  device: string
  status: string
  risk_score: number | null
  risk_level: string | null
  risk_factors: RiskFactors | null
  is_fraud_label: boolean | null
  data_source: string
}

export interface Alert {
  id: number
  transaction_pk: number
  customer_id: string
  risk_score: number
  risk_level: string
  triggered_rules: RuleHit[]
  factors: RiskFactors
  status: string
  case_id: number | null
  created_at: string
  transaction: Transaction | null
}

export interface Rule {
  id: number
  name: string
  description: string
  rule_type: string
  parameters: Record<string, unknown>
  severity: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CaseNote {
  id: number
  body: string
  created_at: string
  author: User
}

export interface Case {
  id: number
  title: string
  description: string
  customer_id: string
  status: string
  priority: string
  opened_by: User
  assigned_to: User | null
  created_at: string
  updated_at: string
  closed_at: string | null
  notes: CaseNote[]
  alerts: Alert[]
}

export interface MLModel {
  id: number
  model_kind: string
  algorithm: string
  feature_names: string[]
  metrics: Record<string, any>
  trained_on: number
  is_active: boolean
  trained_at: string
  trained_by: string
}

export interface Summary {
  total_transactions: number
  transactions_24h: number
  total_volume: number
  volume_24h: number
  total_alerts: number
  open_alerts: number
  open_cases: number
  avg_risk_score: number
}
