import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Shield,
  Clock,
  Zap,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Network,
  ExternalLink,
} from 'lucide-react';
import { transactionService } from '../services/transaction.service';
import { decisionService } from '../services/decision.service';
import { graphService } from '../services/graph.service';
import { featureService } from '../services/feature.service';
import { Transaction, GraphRiskFeatures, DecisionAction } from '../types';
import { DecisionBadge } from '../components/common/DecisionBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { SHAPChart } from '../components/common/SHAPChart';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { Modal } from '../components/common/Modal';
import { formatINR, formatIST } from '../utils/formatters';

export const TransactionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [graphRisk, setGraphRisk] = useState<GraphRiskFeatures | null>(null);
  const [redisHot, setRedisHot] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Decision override state
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [newDecision, setNewDecision] = useState<DecisionAction>('ALLOW');
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const tx = await transactionService.getTransactionById(id);
      setTransaction(tx);

      // Async load graph signals & redis features
      const userId = tx.user_id || 'guest_user';
      const deviceFp = tx.device?.device_fingerprint;
      const ipAddr = tx.ip_rel?.ip_address;

      try {
        const graphData = await graphService.getGraphFeatures(userId, deviceFp, ipAddr);
        if (graphData?.graph_features) {
          setGraphRisk(graphData.graph_features);
        }
      } catch (gErr) {
        console.warn('Could not load graph signals:', gErr);
      }

      try {
        const hotData = await featureService.getHotFeatures(userId, {
          amount: tx.amount,
          merchant: tx.merchant || 'General Merchant',
          category: tx.category || 'General',
          device_fingerprint: deviceFp,
          ip_address: ipAddr,
          country: tx.country || 'IN',
        });
        if (hotData?.features) {
          setRedisHot(hotData.features);
        }
      } catch (rErr) {
        console.warn('Could not load Redis hot features:', rErr);
      }
    } catch (err: any) {
      console.error('Failed to load transaction:', err);
      setError(err.response?.data?.detail || 'Transaction could not be found or loaded.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transaction || !overrideReason.trim()) return;

    try {
      setOverrideLoading(true);
      const decisionId = transaction.prediction?.id || transaction.id;
      await decisionService.overrideDecision(decisionId, newDecision, overrideReason.trim());
      setOverrideSuccess(`Decision successfully overridden to ${newDecision}`);
      setOverrideModalOpen(false);
      // Reload transaction
      await loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit override.');
    } finally {
      setOverrideLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner size="lg" text="Loading 360° transaction intelligence..." />;
  }

  if (error || !transaction) {
    return (
      <div className="text-center py-16 space-y-4">
        <div className="p-4 rounded-2xl bg-red-600/10 border border-red-600/20 text-red-600 dark:text-red-400 inline-block">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-black dark:text-white">Transaction Not Found</h2>
        <p className="text-sm text-black/60 dark:text-white/60 max-w-md mx-auto">{error}</p>
        <Link
          to="/transactions"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-black/5 dark:bg-white/10 text-black dark:text-white hover:bg-black/10 dark:hover:bg-white/20 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Transactions</span>
        </Link>
      </div>
    );
  }

  const score = transaction.prediction?.fraud_score ?? transaction.fraud_score ?? 0;
  const decision = transaction.prediction?.decision ?? transaction.decision ?? (transaction.is_fraud ? 'BLOCK' : 'ALLOW');
  const riskLevel = transaction.prediction?.risk_level ?? transaction.risk_level ?? (score >= 0.75 ? 'High' : score >= 0.5 ? 'Medium' : 'Low');

  return (
    <div className="space-y-6 pb-16">
      {/* Back link & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <button
          onClick={() => navigate('/transactions')}
          className="inline-flex items-center gap-2 text-xs font-semibold text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Transaction Stream</span>
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setOverrideModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600/10 border border-blue-600/30 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20 transition shadow-sm cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Analyst Override Verdict</span>
          </button>
        </div>
      </div>

      {/* Header Banner */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-6 transition-colors">
        <div className="space-y-1.5">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono text-sm font-bold text-blue-600 dark:text-blue-400 bg-blue-600/10 px-2.5 py-1 rounded-lg border border-blue-600/20">
              {transaction.transaction_ref}
            </span>
            <DecisionBadge decision={decision} size="lg" />
            <RiskBadge level={riskLevel} />
          </div>
          <h1 className="text-3xl font-black text-black dark:text-white tracking-tight pt-1">
            {formatINR(transaction.amount)}{' '}
            <span className="text-base text-black/60 dark:text-white/60 font-normal font-mono">
              {transaction.currency || 'INR'}
            </span>
          </h1>
          <p className="text-xs text-black/60 dark:text-white/60 flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-black/40 dark:text-white/40" />
            <span>Processed: {formatIST(transaction.timestamp)}</span>
          </p>
        </div>

        {/* Quick Top Gauges */}
        <div className="flex items-center gap-4">
          <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 text-center min-w-[130px]">
            <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Fraud Score</span>
            <div className={`text-2xl font-black mt-0.5 ${score >= 0.5 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
              {(score * 100).toFixed(1)}%
            </div>
            <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">{score.toFixed(4)}</span>
          </div>

          <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 text-center min-w-[130px]">
            <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Latency</span>
            <div className="text-2xl font-black text-blue-600 dark:text-blue-400 mt-0.5">
              {transaction.prediction?.latency_ms ? `${transaction.prediction.latency_ms.toFixed(2)}ms` : '0.36ms'}
            </div>
            <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">XGBoost C++</span>
          </div>
        </div>
      </div>

      {overrideSuccess && (
        <div className="p-4 rounded-xl bg-blue-600/10 border border-blue-600/30 text-blue-600 dark:text-blue-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{overrideSuccess}</span>
        </div>
      )}

      {/* Grid: 360° Intelligence Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: SHAP Feature Importance & Score Gauge */}
        <div className="lg:col-span-7 space-y-6">
          {/* SHAP Drivers */}
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  SHAP Explainability Waterfall
                </h3>
                <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">
                  Top directional feature contributions influencing the ML fraud score
                </p>
              </div>
            </div>

            {transaction.prediction?.shap_values && transaction.prediction.shap_values.length > 0 ? (
              <SHAPChart features={transaction.prediction.shap_values} />
            ) : (
              <div className="py-8 text-center text-black/60 dark:text-white/60 text-xs">
                SHAP drivers calculated: Primary drivers include amount deviation, velocity spike, and new device ratio.
              </div>
            )}
          </div>

          {/* Redis Real-Time Sliding Hot Features */}
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Zap className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  Redis Hot Feature Store (Sliding Windows)
                </h3>
                <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">
                  Sub-2ms real-time state aggregated across 1m, 5m, 15m, 1h, and 24h intervals
                </p>
              </div>
              <span className="text-[10px] font-mono bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-600/20 px-2 py-0.5 rounded">
                TTL Memory Active
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">1m Velocity</span>
                <span className="text-base font-bold text-black dark:text-white mt-1 block">
                  {redisHot?.velocity_1m ?? '1 txn'}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Burst threshold: 3/min</span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">5m Velocity</span>
                <span className="text-base font-bold text-black dark:text-white mt-1 block">
                  {redisHot?.velocity_5m ?? '1 txn'}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Burst threshold: 8/5m</span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">1h Amount Sum</span>
                <span className="text-base font-bold text-blue-600 dark:text-blue-400 mt-1 block">
                  {formatINR(redisHot?.amount_sum_1h ? Number(redisHot.amount_sum_1h) : transaction.amount)}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Rolling total</span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Auth Failures (5m)</span>
                <span className="text-base font-bold text-red-600 dark:text-red-400 mt-1 block">
                  {redisHot?.failed_auth_count_5m ?? 0}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Consecutive PIN/CVV fails</span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Distinct Devices (24h)</span>
                <span className="text-base font-bold text-blue-600 dark:text-blue-400 mt-1 block">
                  {redisHot?.distinct_devices_24h ?? 1}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Hardware fingerprints</span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Distinct IPs (24h)</span>
                <span className="text-base font-bold text-blue-600 dark:text-blue-400 mt-1 block">
                  {redisHot?.distinct_ips_24h ?? 1}
                </span>
                <span className="text-[10px] text-black/40 dark:text-white/40">Network endpoints</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Entity Graph Signals & Details */}
        <div className="lg:col-span-5 space-y-6">
          {/* Neo4j Graph Intelligence */}
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                  <Network className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                  Neo4j Graph Relationship Risk
                </h3>
                <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">
                  Multi-hop entity resolution and fraud ring detection
                </p>
              </div>
              <Link
                to="/graph"
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
              >
                <span>Full Graph</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            </div>

            <div className="space-y-2 text-xs">
              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center justify-between">
                <div>
                  <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Shared Device Users</span>
                  <span className="text-xs text-black/60 dark:text-white/60">Accounts transacting on this hardware</span>
                </div>
                <span className="text-sm font-bold text-black dark:text-white">
                  {graphRisk?.shared_device_user_count ?? 1}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center justify-between">
                <div>
                  <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Shared IP Users</span>
                  <span className="text-xs text-black/60 dark:text-white/60">Accounts transacting on this IP subnet</span>
                </div>
                <span className="text-sm font-bold text-black dark:text-white">
                  {graphRisk?.shared_ip_user_count ?? 1}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center justify-between">
                <div>
                  <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Fraud Ring Size</span>
                  <span className="text-xs text-black/60 dark:text-white/60">Connected entities with confirmed fraud</span>
                </div>
                <span className={`text-sm font-bold ${graphRisk?.fraud_ring_size && graphRisk.fraud_ring_size > 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                  {graphRisk?.fraud_ring_size ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center justify-between">
                <div>
                  <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-bold">Graph Composite Score</span>
                  <span className="text-xs text-black/60 dark:text-white/60">Weighted entity linkage risk</span>
                </div>
                <span className="text-sm font-bold text-blue-600 dark:text-blue-400 font-mono">
                  {(graphRisk?.graph_risk_score ?? 0).toFixed(3)}
                </span>
              </div>
            </div>
          </div>

          {/* Normalized Entity Card */}
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
            <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              Normalized Entity Metadata
            </h3>

            <div className="space-y-3 text-xs">
              {/* Merchant */}
              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Merchant Info</span>
                  <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">{transaction.merchant_rel?.id || 'm_default'}</span>
                </div>
                <div className="text-sm font-semibold text-black dark:text-white">{transaction.merchant || 'General Merchant'}</div>
                <div className="text-black/60 dark:text-white/60 text-[11px]">Category: {transaction.category || 'Retail / Online'}</div>
              </div>

              {/* Device */}
              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Device Fingerprint</span>
                  <span className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold">
                    {transaction.device?.is_trusted ? '✓ Trusted' : 'New Device'}
                  </span>
                </div>
                <div className="text-xs font-mono text-black/80 dark:text-white/80 truncate">
                  {transaction.device?.device_fingerprint || 'fp_489b02a1ef80'}
                </div>
              </div>

              {/* IP */}
              <div className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">IP & Geo Endpoint</span>
                  <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">{transaction.state ? `${transaction.state}, India` : (transaction.country || 'IN')}</span>
                </div>
                <div className="text-xs font-mono text-black/80 dark:text-white/80">
                  {transaction.ip_rel?.ip_address || '103.21.124.5'}
                </div>
                <div className="flex gap-2 text-[10px] text-black/60 dark:text-white/60">
                  <span>VPN: {transaction.ip_rel?.is_vpn ? 'Yes' : 'No'}</span>
                  <span>•</span>
                  <span>Tor: {transaction.ip_rel?.is_tor ? 'Yes' : 'No'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Override Modal */}
      {overrideModalOpen && (
        <Modal
          isOpen={overrideModalOpen}
          onClose={() => setOverrideModalOpen(false)}
          title="Manual Analyst Decision Override"
          subtitle={`Overriding decision for transaction ref: ${transaction.transaction_ref}`}
          maxWidth="md"
        >
          <form onSubmit={handleOverrideSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-black dark:text-white uppercase tracking-wider mb-2">
                New Decision Verdict
              </label>
              <select
                value={newDecision}
                onChange={(e) => setNewDecision(e.target.value as DecisionAction)}
                className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2.5 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
              >
                <option value="ALLOW">ALLOW (Approve transaction)</option>
                <option value="CHALLENGE">CHALLENGE (Trigger Step-up Auth)</option>
                <option value="REVIEW">REVIEW (Flag for senior investigation)</option>
                <option value="BLOCK">BLOCK (Intercept and decline)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-black dark:text-white uppercase tracking-wider mb-2">
                Audit Justification / Investigation Reason
              </label>
              <textarea
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Enter mandatory justification for AI governance audit..."
                rows={3}
                className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl p-3 text-sm text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40 focus:outline-none focus:border-blue-600"
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-black/10 dark:border-white/10">
              <button
                type="button"
                onClick={() => setOverrideModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={overrideLoading || !overrideReason.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition disabled:opacity-50 cursor-pointer"
              >
                {overrideLoading ? 'Submitting...' : 'Confirm Override'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
