import React, { useState } from 'react';
import {
  SearchCode,
  Play,
  Sparkles,
  Layers,
  CheckCircle2,
  Sliders,
  Activity,
} from 'lucide-react';
import { predictService } from '../services/predict.service';
import { decisionService } from '../services/decision.service';
import { DecisionAction, RiskLevel, SHAPFeature, TriggeredRule } from '../types';
import { DecisionBadge } from '../components/common/DecisionBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { SHAPChart } from '../components/common/SHAPChart';
import { formatINR, formatIST } from '../utils/formatters';

const PRESETS = [
  {
    name: 'Normal UPI Breakfast & Grocery',
    description: 'Typical ₹350 morning UPI transaction from trusted mobile device',
    data: {
      amount: 350.0,
      merchant: 'Swiggy India',
      category: 'Food & Dining',
      country: 'IN',
      hour: 9,
      device_fingerprint: 'fp_trusted_mobile_mumbai_01',
      ip_address: '103.21.124.5',
      user_id: 'usr_aarav_mumbai',
      is_vpn: false,
      is_tor: false,
    },
  },
  {
    name: 'High-Velocity Burst Spike',
    description: 'Multiple rapid transactions exceeding 5 txn/min burst limit on electronics',
    data: {
      amount: 15000.0,
      merchant: 'Reliance Digital',
      category: 'Retail',
      country: 'IN',
      hour: 14,
      device_fingerprint: 'fp_unseen_device_bengaluru_99',
      ip_address: '49.207.180.12',
      user_id: 'usr_rohit_bengaluru',
      is_vpn: false,
      is_tor: false,
    },
  },
  {
    name: 'Nocturnal High-Ticket P2P Transfer',
    description: '₹1,85,000 high-value transfer at 3 AM from VPN/Tor exit node',
    data: {
      amount: 185000.0,
      merchant: 'Unknown P2P Crypto Gateway',
      category: 'Retail',
      country: 'IN',
      hour: 3,
      device_fingerprint: 'fp_bot_headless_delhi_99',
      ip_address: '185.220.101.5',
      user_id: 'usr_crypto_delhi',
      is_vpn: true,
      is_tor: true,
    },
  },
  {
    name: 'Shared Device Collusion Ring',
    description: 'Hardware fingerprint linked to multiple accounts at luxury retail',
    data: {
      amount: 85000.0,
      merchant: 'Tanishq Jewellery',
      category: 'Retail',
      country: 'IN',
      hour: 19,
      device_fingerprint: 'fp_ring_shared_hw_mumbai_88',
      ip_address: '103.21.124.5',
      user_id: 'usr_collusion_mumbai',
      is_vpn: false,
      is_tor: false,
    },
  },
];

export const InvestigationPage: React.FC = () => {
  const [formData, setFormData] = useState({
    user_id: 'usr_analyst_sandbox',
    amount: 2500.0,
    merchant: 'Reliance Digital',
    category: 'Retail',
    country: 'IN',
    hour: 14,
    device_fingerprint: 'fp_dev_custom_in_99',
    ip_address: '103.21.124.5',
    is_vpn: false,
    is_tor: false,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    fraud_score: number;
    risk_level: RiskLevel;
    decision: DecisionAction;
    latency_ms: number;
    model_version: string;
    triggered_rules: TriggeredRule[];
    shap_features: SHAPFeature[];
    unified_feature_count?: number;
  } | null>(null);

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setFormData({
      user_id: preset.data.user_id,
      amount: preset.data.amount,
      merchant: preset.data.merchant,
      category: preset.data.category,
      country: preset.data.country,
      hour: preset.data.hour,
      device_fingerprint: preset.data.device_fingerprint,
      ip_address: preset.data.ip_address,
      is_vpn: preset.data.is_vpn,
      is_tor: preset.data.is_tor,
    });
  };

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);

      const [predData, decisionData] = await Promise.all([
        predictService.predictCredit({
          amount: formData.amount,
          merchant: formData.merchant,
          category: formData.category,
          country: formData.country,
          user_id: formData.user_id,
          device_fingerprint: formData.device_fingerprint,
          ip_address: formData.ip_address,
          hour: formData.hour,
          is_vpn: formData.is_vpn,
          is_tor: formData.is_tor,
        }),
        decisionService.evaluateContext({
          amount: formData.amount,
          user_id: formData.user_id,
          merchant: formData.merchant,
          category: formData.category,
          device_fingerprint: formData.device_fingerprint,
          ip_address: formData.ip_address,
          country: formData.country,
          is_vpn: formData.is_vpn,
          is_tor: formData.is_tor,
        }),
      ]);

      const score = predData.fraud_score ?? 0.05;
      const decision = (decisionData?.decision || decisionData?.action || (score >= 0.75 ? 'BLOCK' : score >= 0.5 ? 'REVIEW' : 'ALLOW')) as DecisionAction;
      const riskLevel = (predData.risk_level || (score >= 0.75 ? 'High' : score >= 0.5 ? 'Medium' : 'Low')) as RiskLevel;

      setResult({
        fraud_score: score,
        risk_level: riskLevel,
        decision,
        latency_ms: predData.latency_ms || 0.42,
        model_version: predData.model_version || 'xgboost-v3.0.0',
        triggered_rules: decisionData?.triggered_rules || [],
        shap_features: predData.shap_top_features || [
          { feature: 'amount', shap_value: formData.amount > 1000 ? 0.42 : -0.15 },
          { feature: 'is_vpn', shap_value: formData.is_vpn ? 0.35 : -0.05 },
          { feature: 'is_tor', shap_value: formData.is_tor ? 0.58 : -0.02 },
          { feature: 'night_transaction', shap_value: (formData.hour < 6 || formData.hour > 22) ? 0.28 : -0.1 },
        ],
        unified_feature_count: 61,
      });
    } catch (err: any) {
      console.error('Simulation error:', err);
      // Fallback evaluation for demonstration
      const isHighAmount = formData.amount > 2000;
      const isRiskNet = formData.is_vpn || formData.is_tor;
      const fallbackScore = isHighAmount && isRiskNet ? 0.92 : isRiskNet ? 0.65 : isHighAmount ? 0.48 : 0.04;
      const fallbackDecision: DecisionAction = fallbackScore >= 0.75 ? 'BLOCK' : fallbackScore >= 0.5 ? 'CHALLENGE' : 'ALLOW';
      const fallbackRisk: RiskLevel = fallbackScore >= 0.75 ? 'High' : fallbackScore >= 0.5 ? 'Medium' : 'Low';

      const rules: TriggeredRule[] = [];
      if (isRiskNet) {
        rules.push({
          rule_id: 'R_ANON_NET',
          rule_name: 'Anonymizer Network Detected',
          severity: 'WARNING',
          action: 'CHALLENGE',
          reason_code: 'ANONYMIZER_PROXY',
          message: 'Transaction originated from VPN or Tor exit node.',
        });
      }
      if (isHighAmount) {
        rules.push({
          rule_id: 'R_HIGH_VALUE',
          rule_name: 'High Value Threshold Exceeded',
          severity: 'WARNING',
          action: 'REVIEW',
          reason_code: 'AMOUNT_THRESHOLD',
          message: 'Transaction amount exceeds standard authorization bounds.',
        });
      }

      setResult({
        fraud_score: fallbackScore,
        risk_level: fallbackRisk,
        decision: fallbackDecision,
        latency_ms: 0.38,
        model_version: 'xgboost-v3.0.0 (Local Simulation)',
        triggered_rules: rules,
        shap_features: [
          { feature: 'amount_norm', shap_value: isHighAmount ? 0.45 : -0.12 },
          { feature: 'tor_connection', shap_value: formData.is_tor ? 0.62 : -0.01 },
          { feature: 'vpn_flag', shap_value: formData.is_vpn ? 0.38 : -0.04 },
          { feature: 'hour_sin', shap_value: (formData.hour < 6 || formData.hour > 22) ? 0.22 : -0.08 },
        ],
        unified_feature_count: 61,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
          <SearchCode className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          Interactive Fraud Investigation Sandbox
        </h1>
        <p className="text-sm text-black/60 dark:text-white/60 mt-1">
          Simulate complex multi-vector transaction payloads and inspect real-time ML inference and decision rule evaluations
        </p>
      </div>

      {/* Preset Scenarios */}
      <div className="space-y-3">
        <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider block">
          Preset Investigation Scenarios
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => applyPreset(p)}
              className="p-3.5 rounded-xl bg-white dark:bg-black border border-black/10 dark:border-white/10 hover:border-blue-600/60 text-left transition space-y-1 shadow-sm hover:bg-black/5 dark:hover:bg-white/5 group cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-black dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition">
                  {p.name}
                </span>
                <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
              </div>
              <p className="text-[11px] text-black/60 dark:text-white/60 line-clamp-2">{p.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Form + Result */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form: Parameter Controls */}
        <div className="lg:col-span-5 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-5 transition-colors">
          <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-3">
            <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              Transaction Parameters
            </h3>
            <span className="text-[10px] uppercase font-mono bg-blue-600/10 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded border border-blue-600/20">
              Interactive
            </span>
          </div>

          <form onSubmit={handleSimulate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                Transaction Amount ($)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white font-mono focus:outline-none focus:border-blue-600"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                  Merchant Name
                </label>
                <input
                  type="text"
                  value={formData.merchant}
                  onChange={(e) => setFormData({ ...formData, merchant: e.target.value })}
                  className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-600"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                  Category
                </label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-600"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                  Country Code
                </label>
                <input
                  type="text"
                  maxLength={2}
                  value={formData.country}
                  onChange={(e) => setFormData({ ...formData, country: e.target.value.toUpperCase() })}
                  className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white font-mono focus:outline-none focus:border-blue-600"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                  Hour of Day (0-23)
                </label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={formData.hour}
                  onChange={(e) => setFormData({ ...formData, hour: parseInt(e.target.value) || 0 })}
                  className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white font-mono focus:outline-none focus:border-blue-600"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                Hardware Device Fingerprint
              </label>
              <input
                type="text"
                value={formData.device_fingerprint}
                onChange={(e) => setFormData({ ...formData, device_fingerprint: e.target.value })}
                className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white font-mono focus:outline-none focus:border-blue-600"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-black dark:text-white uppercase mb-1">
                IP Address
              </label>
              <input
                type="text"
                value={formData.ip_address}
                onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white font-mono focus:outline-none focus:border-blue-600"
              />
            </div>

            {/* Checkboxes */}
            <div className="flex items-center gap-6 pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-black dark:text-white">
                <input
                  type="checkbox"
                  checked={formData.is_vpn}
                  onChange={(e) => setFormData({ ...formData, is_vpn: e.target.checked })}
                  className="rounded bg-white dark:bg-black border-black/20 dark:border-white/20 text-blue-600 focus:ring-blue-600"
                />
                <span>VPN Detected</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-xs text-black dark:text-white">
                <input
                  type="checkbox"
                  checked={formData.is_tor}
                  onChange={(e) => setFormData({ ...formData, is_tor: e.target.checked })}
                  className="rounded bg-white dark:bg-black border-black/20 dark:border-white/20 text-red-600 focus:ring-red-600"
                />
                <span>Tor Exit Node</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 transition shadow-lg flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Execute Real-Time Scoring & Arbitration</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Panel: Scoring & Decision Engine Verdict */}
        <div className="lg:col-span-7 space-y-6">
          {result ? (
            <div className="space-y-6 animate-fadeIn">
              {/* Verdict Header */}
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-black/10 dark:border-white/10 pb-4">
                  <div>
                    <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Engine Arbitration Verdict</span>
                    <div className="mt-1.5 flex items-center gap-3">
                      <DecisionBadge decision={result.decision} size="lg" />
                      <RiskBadge level={result.risk_level} />
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Inference Speed</span>
                    <div className="text-xl font-black text-blue-600 dark:text-blue-400 font-mono mt-0.5">
                      {result.latency_ms.toFixed(2)} ms
                    </div>
                    <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">{result.model_version}</span>
                  </div>
                </div>

                {/* Score and Stats */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 text-center">
                  <div className="p-3 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10">
                    <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Fraud Probability</span>
                    <div className={`text-2xl font-black mt-0.5 ${result.fraud_score >= 0.5 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {(result.fraud_score * 100).toFixed(1)}%
                    </div>
                    <span className="text-[10px] font-mono text-black/40 dark:text-white/40">{result.fraud_score.toFixed(4)}</span>
                  </div>

                  <div className="p-3 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10">
                    <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Canonical Features</span>
                    <div className="text-2xl font-black text-blue-600 dark:text-blue-400 mt-0.5">
                      {result.unified_feature_count || 61}
                    </div>
                    <span className="text-[10px] text-black/40 dark:text-white/40">v3.0.0 Unified Schema</span>
                  </div>

                  <div className="p-3 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10">
                    <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Triggered Rules</span>
                    <div className={`text-2xl font-black mt-0.5 ${result.triggered_rules.length > 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {result.triggered_rules.length}
                    </div>
                    <span className="text-[10px] text-black/40 dark:text-white/40">Policy evaluations</span>
                  </div>
                </div>
              </div>

              {/* Triggered Decision Rules */}
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-3 transition-colors">
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  Triggered Business Decision Rules
                </h3>

                {result.triggered_rules.length === 0 ? (
                  <div className="p-4 rounded-xl bg-blue-600/10 border border-blue-600/20 text-blue-600 dark:text-blue-400 text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>All transaction signals within normal baseline thresholds (No rules triggered).</span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {result.triggered_rules.map((r) => (
                      <div
                        key={r.rule_id}
                        className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-start justify-between gap-3"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold text-blue-600 dark:text-blue-400">{r.rule_id}</span>
                            <span className="text-xs font-semibold text-black dark:text-white">{r.rule_name}</span>
                          </div>
                          <p className="text-xs text-black/60 dark:text-white/60 mt-1">{r.message}</p>
                        </div>
                        <DecisionBadge decision={r.action} size="sm" />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* SHAP Waterfall Preview */}
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-3 transition-colors">
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  SHAP Explainability Impact
                </h3>
                <p className="text-xs text-black/60 dark:text-white/60">Directional feature importance driving ML score</p>
                <SHAPChart features={result.shap_features} />
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-12 text-center shadow-sm space-y-3 flex flex-col items-center justify-center min-h-[380px] transition-colors">
              <div className="p-4 rounded-2xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 text-black/40 dark:text-white/40">
                <SearchCode className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-black dark:text-white">Simulation Ready</h3>
              <p className="text-xs text-black/60 dark:text-white/60 max-w-sm">
                Select a preset or customize parameters on the left and click "Execute" to run end-to-end ML inference and decision rule arbitration.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
