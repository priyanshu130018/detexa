export type RiskLevel = 'Low' | 'Medium' | 'High';
export type DecisionAction = 'ALLOW' | 'CHALLENGE' | 'REVIEW' | 'BLOCK';
export type AlertStatus = 'open' | 'reviewed' | 'resolved' | 'false_positive';

export interface User {
  id: string;
  name: string;
  email: string;
  mobile?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  last_login?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  name: string;
  email: string;
  is_admin: boolean;
}

export interface SHAPFeature {
  feature: string;
  shap_value: number;
}

export interface TriggeredRule {
  rule_id: string;
  rule_name: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  action: DecisionAction;
  reason_code: string;
  message: string;
}

export interface FraudPredictionResult {
  transaction_id: string;
  transaction_ref?: string;
  fraud_score: number;
  risk_level: RiskLevel;
  decision: DecisionAction;
  is_fraud: boolean;
  primary_reason?: string;
  reason_codes?: string[];
  requires_step_up_auth?: boolean;
  shap_top_features?: SHAPFeature[];
  model_version: string;
  latency_ms: number;
  inference_engine?: string;
}

export interface BatchCreditFraudResult {
  total_processed: number;
  fraud_detected_count: number;
  predictions: FraudPredictionResult[];
  batch_latency_ms: number;
}

export interface BehaviorPredictionResult {
  session_id: string;
  anomaly_score: number;
  risk_level: RiskLevel;
  is_anomalous: boolean;
  risk_factors: string[];
  latency_ms: number;
}

export interface BehaviorLog {
  id: string;
  user_id?: string;
  session_id: string;
  ip_address: string;
  geo_country?: string;
  geo_city?: string;
  is_vpn: boolean;
  is_tor: boolean;
  typing_speed_wpm?: number;
  typing_speed?: number;
  mouse_velocity: number;
  login_hour: number;
  device_change?: boolean;
  anomaly_score: number;
  risk_level: RiskLevel;
  is_anomalous: boolean;
  timestamp: string;
}

export interface BehaviorStats {
  total_sessions: number;
  anomalous_sessions: number;
  anomaly_rate: number;
  high_risk_sessions: number;
  medium_risk_sessions: number;
  low_risk_sessions: number;
  vpn_count: number;
  tor_count: number;
  avg_typing_speed: number;
  avg_mouse_velocity: number;
  average_anomaly_score?: number;
}

export interface Merchant {
  id: string;
  name: string;
  category: string;
  risk_score?: number;
  created_at?: string;
}

export interface Device {
  id: string;
  device_fingerprint: string;
  user_agent?: string;
  is_trusted: boolean;
  first_seen_at: string;
  last_seen_at: string;
}

export interface IPAddress {
  id: string;
  ip_address: string;
  geo_country?: string;
  geo_city?: string;
  is_vpn: boolean;
  is_tor: boolean;
  reputation_score: number;
  last_checked_at: string;
}

export interface Transaction {
  id: string;
  user_id?: string;
  customer_id?: string;
  transaction_ref: string;
  amount: number;
  transaction_amount?: number;
  merchant?: string;
  category?: string;
  merchant_category?: string;
  country?: string;
  state?: string;
  currency?: string;
  account_type?: string;
  transaction_type?: string;
  transaction_direction?: string;
  account_balance?: number;
  credit_score?: number;
  has_loan?: number | boolean;
  loan_type?: string;
  emi_amount?: number;
  transaction_status?: string;
  channel?: string;
  kyc_status?: string;
  transaction_hour?: number;
  transaction_date?: string;
  transaction_time?: string;
  fraud_score?: number;
  risk_level?: RiskLevel;
  decision?: DecisionAction;
  is_fraud: boolean;
  timestamp: string;
  // Normalized Relations
  user?: User;
  merchant_rel?: Merchant;
  device?: Device;
  ip_rel?: IPAddress;
  prediction?: {
    id: string;
    fraud_score: number;
    risk_level: RiskLevel;
    decision: DecisionAction;
    shap_values?: SHAPFeature[];
    latency_ms: number;
    model_version: string;
  };
  alert?: Alert;
}

export interface Alert {
  id: string;
  user_id?: string;
  transaction_id?: string;
  alert_type: string;
  risk_level: RiskLevel;
  score: number;
  description: string;
  status: AlertStatus;
  shap_values?: SHAPFeature[];
  metadata?: Record<string, any>;
  created_at: string;
  resolved_at?: string;
}

export interface DashboardStats {
  total_transactions: number;
  fraud_count: number;
  fraud_rate: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  total_alerts: number;
  open_alerts: number;
  avg_fraud_score: number;
  cached?: boolean;
}

export interface DecisionStats {
  total_decisions: number;
  allow_count: number;
  challenge_count: number;
  review_count: number;
  block_count: number;
  allow_percentage: number;
  challenge_percentage: number;
  review_percentage: number;
  block_percentage: number;
}

export interface GraphRiskFeatures {
  user_id: string;
  device_fingerprint?: string;
  ip_address?: string;
  shared_device_user_count: number;
  shared_ip_user_count: number;
  shared_device_fraud_count: number;
  shared_ip_fraud_count: number;
  associated_merchant_count: number;
  fraud_ring_size: number;
  is_device_shared: boolean;
  is_ip_shared: boolean;
  graph_risk_score: number;
}

export interface FraudRing {
  ring_id: string;
  entity_type: string;
  entity_key: string;
  user_count: number;
  associated_users: string[];
  associated_transactions: string[];
  confirmed_fraud_count: number;
  total_fraud_amount: number;
  risk_level: string;
  description: string;
}

export interface GraphNode {
  id: string;
  label: string;
  title: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

export interface SubgraphData {
  root_id: string;
  entity_type: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}
