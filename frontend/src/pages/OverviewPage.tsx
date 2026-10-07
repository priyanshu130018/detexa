import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  CreditCard,
  ShieldAlert,
  AlertTriangle,
  Bell,
  Activity,
  RefreshCw,
  Eye,
  ArrowRight,
  ExternalLink,
  Radio,
} from 'lucide-react';
import {
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts';
import { alertService } from '../services/alert.service';
import { transactionService } from '../services/transaction.service';
import { decisionService } from '../services/decision.service';
import { useRealtime } from '../context/RealtimeContext';
import { useTheme } from '../context/ThemeContext';
import { Alert, DashboardStats, DecisionStats, Transaction } from '../types';
import { StatCard } from '../components/common/StatCard';
import { RiskBadge } from '../components/common/RiskBadge';
import { DecisionBadge } from '../components/common/DecisionBadge';
import { Modal } from '../components/common/Modal';
import { SHAPChart } from '../components/common/SHAPChart';

const DECISION_COLORS: Record<string, string> = {
  ALLOW: '#2563eb',
  CHALLENGE: '#3b82f6',
  REVIEW: '#ef4444',
  BLOCK: '#dc2626',
};

export const OverviewPage: React.FC = () => {
  const { connectionState, reconnect, subscribe, simulateEvent } = useRealtime();
  const { isDark } = useTheme();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [decisionStats, setDecisionStats] = useState<DecisionStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null);
  const [, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [newlyArrivedTxId, setNewlyArrivedTxId] = useState<string | null>(null);

  // Initial Snapshot Fetch
  const fetchData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [statsData, decStatsData, alertsData, txnsData] = await Promise.all([
        alertService.getDashboardStats().catch(() => null),
        decisionService.getDecisionStats().catch(() => null),
        alertService.getAlerts({ limit: 6 }).catch(() => []),
        transactionService.getTransactions({ limit: 50 }).catch(() => []),
      ]);

      if (statsData) setStats(statsData);
      if (decStatsData) setDecisionStats(decStatsData);
      if (alertsData) setAlerts(alertsData);
      if (txnsData) setTransactions(txnsData);
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Real-Time Event Subscriptions (No Polling!)
  useEffect(() => {
    const unsubTx = subscribe('new_transaction', (data: any) => {
      const newTx: Transaction = {
        id: data.id || data.transaction_id || `tx_${Date.now()}`,
        transaction_ref: data.transaction_ref || `TXN-${Date.now()}`,
        amount: Number(data.amount || 0),
        merchant: data.merchant,
        category: data.category,
        timestamp: data.timestamp || new Date().toISOString(),
        fraud_score: data.fraud_score ?? data.fraud_probability ?? 0.05,
        is_fraud: data.is_fraud ?? false,
        risk_level: data.risk_level ?? 'Low',
        decision: data.decision ?? 'ALLOW',
        user_id: data.user_id,
        country: data.country,
        currency: data.currency || 'USD',
        prediction: data.prediction,
      };

      setTransactions((prev) => [newTx, ...prev.slice(0, 49)]);
      setNewlyArrivedTxId(newTx.id);
      setTimeout(() => setNewlyArrivedTxId(null), 2500);

      setStats((prev) => {
        if (!prev) return prev;
        const total = prev.total_transactions + 1;
        const isFraud = newTx.is_fraud || newTx.decision === 'BLOCK';
        const fraudCount = prev.fraud_count + (isFraud ? 1 : 0);
        return {
          ...prev,
          total_transactions: total,
          fraud_count: fraudCount,
          fraud_rate: fraudCount / total,
          avg_fraud_score: (prev.avg_fraud_score * (total - 1) + (newTx.fraud_score || 0)) / total,
        };
      });
    });

    const unsubAlert = subscribe('fraud_alert', (data: any) => {
      const newAlert: Alert = {
        id: data.alert_id || data.id || `alt_${Date.now()}`,
        transaction_id: data.transaction_id || `tx_${Date.now()}`,
        alert_type: data.alert_type || 'ML_ANOMALY',
        risk_level: data.risk_level || 'High',
        score: Number(data.fraud_score || data.score || 0.88),
        status: 'open',
        description: data.reason || data.description || 'Elevated anomaly score detected.',
        created_at: data.timestamp || new Date().toISOString(),
      };

      setAlerts((prev) => [newAlert, ...prev.slice(0, 9)]);
      setStats((prev) => prev ? { ...prev, open_alerts: prev.open_alerts + 1 } : prev);
    });

    const unsubDecision = subscribe('decision_event', (data: any) => {
      setDecisionStats((prev) => {
        if (!prev) return prev;
        const action = (data.decision || data.action || '').toUpperCase();
        return {
          ...prev,
          total_decisions: prev.total_decisions + 1,
          allow_count: action === 'ALLOW' ? prev.allow_count + 1 : prev.allow_count,
          block_count: action === 'BLOCK' ? prev.block_count + 1 : prev.block_count,
          review_count: action === 'REVIEW' ? prev.review_count + 1 : prev.review_count,
          challenge_count: action === 'CHALLENGE' ? prev.challenge_count + 1 : prev.challenge_count,
        };
      });
    });

    return () => {
      unsubTx();
      unsubAlert();
      unsubDecision();
    };
  }, [subscribe]);

  // Aggregate transaction volumes by time
  const volumeMap: Record<string, { time: string; total: number; blocked: number; review: number }> = {};
  transactions.slice(0, 30).forEach((t) => {
    const timeLabel = new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (!volumeMap[timeLabel]) {
      volumeMap[timeLabel] = { time: timeLabel, total: 0, blocked: 0, review: 0 };
    }
    volumeMap[timeLabel].total += 1;
    if (t.decision === 'BLOCK' || t.is_fraud) volumeMap[timeLabel].blocked += 1;
    if (t.decision === 'REVIEW') volumeMap[timeLabel].review += 1;
  });
  const volumeTrend = Object.values(volumeMap).reverse();

  // Decision distribution data
  const decisionData = [
    { name: 'ALLOW', value: decisionStats?.allow_count || 0, color: DECISION_COLORS.ALLOW },
    { name: 'CHALLENGE', value: decisionStats?.challenge_count || 0, color: DECISION_COLORS.CHALLENGE },
    { name: 'REVIEW', value: decisionStats?.review_count || 0, color: DECISION_COLORS.REVIEW },
    { name: 'BLOCK', value: decisionStats?.block_count || 0, color: DECISION_COLORS.BLOCK },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight">
              Fraud Defense Operations
            </h1>
            {connectionState === 'connected' ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 animate-pulse" />
                <span>WebSocket Connected (Real-Time Push)</span>
              </span>
            ) : connectionState === 'reconnecting' ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 animate-pulse">
                <RefreshCw className="w-3 h-3 animate-spin text-blue-600 dark:text-blue-400" />
                <span>Reconnecting Real-Time Stream...</span>
              </span>
            ) : (
              <button
                onClick={reconnect}
                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-600/10 text-red-600 dark:text-red-400 border border-red-500/30 hover:bg-red-600/20 transition cursor-pointer"
              >
                <span>Stream Disconnected (Click to Reconnect)</span>
              </button>
            )}
          </div>
          <p className="text-sm text-black/60 dark:text-white/60 mt-1">
            Real-time event stream, multi-layer ML inference, and automated decision arbitrations (Zero Polling)
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => simulateEvent('new_transaction')}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20 transition shadow-sm cursor-pointer"
          >
            <Radio className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 animate-pulse" />
            <span>Simulate Incoming Event</span>
          </button>

          <button
            onClick={fetchData}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-black border border-black/10 dark:border-white/10 text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/10 transition disabled:opacity-50 cursor-pointer shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-blue-500' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Resync Snapshot'}</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Transactions"
          value={stats?.total_transactions.toLocaleString() || '0'}
          subtitle="Real-time stream count"
          icon={CreditCard}
          color="blue"
        />
        <StatCard
          title="Fraud Block Rate"
          value={`${((decisionStats?.block_percentage || stats?.fraud_rate || 0) * (decisionStats?.block_percentage ? 1 : 100)).toFixed(1)}%`}
          subtitle={`${decisionStats?.block_count || stats?.fraud_count || 0} transactions blocked`}
          icon={ShieldAlert}
          color="red"
        />
        <StatCard
          title="Step-Up Challenges"
          value={decisionStats?.challenge_count?.toLocaleString() || '0'}
          subtitle={`${(decisionStats?.challenge_percentage || 0).toFixed(1)}% MFA step-up rate`}
          icon={AlertTriangle}
          color="blue"
        />
        <StatCard
          title="Open Alerts"
          value={stats?.open_alerts.toLocaleString() || '0'}
          subtitle="Pending analyst review"
          icon={Bell}
          color="red"
        />
        <StatCard
          title="Avg Fraud Score"
          value={(stats?.avg_fraud_score || 0).toFixed(3)}
          subtitle="Live XGBoost score"
          icon={Activity}
          color="blue"
        />
      </div>

      {/* Visualizations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Real-time Activity Trend */}
        <div className="lg:col-span-8 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm transition-colors">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-black dark:text-white">Transaction Stream & Interceptions</h3>
              <p className="text-xs text-black/60 dark:text-white/60">Total volume vs automated blocks & analyst reviews</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1.5 text-black/70 dark:text-white/70">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> Total
              </span>
              <span className="flex items-center gap-1.5 text-black/70 dark:text-white/70">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600" /> Blocked
              </span>
              <span className="flex items-center gap-1.5 text-black/70 dark:text-white/70">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400" /> Review
              </span>
            </div>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={volumeTrend.length > 0 ? volumeTrend : [{ time: 'Now', total: 1, blocked: 0, review: 0 }]}>
                <defs>
                  <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="blockGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#dc2626" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke={isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)"} tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }} />
                <YAxis stroke={isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)"} tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#000000' : '#ffffff',
                    borderColor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)',
                    borderRadius: '8px',
                    color: isDark ? '#ffffff' : '#000000',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                  itemStyle={{ color: isDark ? '#ffffff' : '#000000' }}
                />
                <Area type="monotone" dataKey="total" stroke="#2563eb" fillOpacity={1} fill="url(#totalGrad)" />
                <Area type="monotone" dataKey="blocked" stroke="#dc2626" fillOpacity={1} fill="url(#blockGrad)" />
                <Area type="monotone" dataKey="review" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Decision Breakdown Donut */}
        <div className="lg:col-span-4 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm flex flex-col justify-between transition-colors">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-black dark:text-white">Decision Breakdown</h3>
              <Link to="/statistics" className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1">
                Details <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">Automated policy arbitration</p>
          </div>

          <div className="h-48 w-full relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={decisionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={48}
                  outerRadius={72}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {decisionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#000000' : '#ffffff',
                    borderColor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)',
                    borderRadius: '8px',
                    color: isDark ? '#ffffff' : '#000000',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                  itemStyle={{ color: isDark ? '#ffffff' : '#000000' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-black/10 dark:border-white/10">
            {decisionData.map((d) => (
              <div key={d.name} className="flex items-center justify-between p-2 rounded-lg bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                  <span className="font-semibold text-black/80 dark:text-white/80">{d.name}</span>
                </div>
                <span className="font-bold text-black dark:text-white">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live Transactions Feed */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-black dark:text-white">⚡ Live Transaction Stream</h3>
              <span className="px-2 py-0.5 text-[10px] font-bold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30 rounded-md animate-pulse">
                WebSocket Live Push
              </span>
            </div>
            <p className="text-xs text-black/60 dark:text-white/60">Transactions pushed instantly as they occur</p>
          </div>
          <Link
            to="/transactions"
            className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 self-start sm:self-auto"
          >
            <span>View All Transactions</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-black dark:text-white">
            <thead className="text-[11px] uppercase tracking-wider bg-black/5 dark:bg-white/5 text-black/60 dark:text-white/60 border-b border-black/10 dark:border-white/10">
              <tr>
                <th className="px-4 py-3">Reference</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Merchant</th>
                <th className="px-4 py-3">Fraud Score</th>
                <th className="px-4 py-3">Risk Tier</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/10 dark:divide-white/10">
              {transactions.slice(0, 8).map((tx) => {
                const score = tx.prediction?.fraud_score ?? tx.fraud_score ?? 0;
                const decision = tx.prediction?.decision ?? tx.decision ?? (tx.is_fraud ? 'BLOCK' : 'ALLOW');
                const riskLevel = tx.prediction?.risk_level ?? tx.risk_level ?? (score >= 0.75 ? 'High' : score >= 0.5 ? 'Medium' : 'Low');
                const isJustArrived = tx.id === newlyArrivedTxId;

                return (
                  <tr
                    key={tx.id}
                    className={`transition-all duration-700 ${
                      isJustArrived
                        ? 'bg-blue-600/15 border-l-4 border-blue-500'
                        : 'hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 dark:text-blue-400 font-semibold">
                      {tx.transaction_ref}
                    </td>
                    <td className="px-4 py-3 font-bold text-black dark:text-white">
                      ${tx.amount.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-xs text-black/80 dark:text-white/80">
                      <div>{tx.merchant || 'Online Merchant'}</div>
                      <span className="text-[10px] text-black/40 dark:text-white/40">{tx.category || 'General'}</span>
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-xs">
                      <span className={score >= 0.75 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}>
                        {score.toFixed(3)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge level={riskLevel} />
                    </td>
                    <td className="px-4 py-3">
                      <DecisionBadge decision={decision} size="sm" />
                    </td>
                    <td className="px-4 py-3 text-xs text-black/60 dark:text-white/60 font-mono">
                      {new Date(tx.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setSelectedTx(tx)}
                        className="p-1.5 rounded-lg bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20 text-black dark:text-white transition inline-flex items-center gap-1 text-xs cursor-pointer"
                        title="Inspect Transaction"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Inspect</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Security Alerts Queue */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-black dark:text-white">🚨 Active Security Incidents</h3>
            <p className="text-xs text-black/60 dark:text-white/60">Real-time alerts triggered by AI heuristics and graph collusion engines</p>
          </div>
          <Link
            to="/alerts"
            className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
          >
            <span>Triage Center</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {alerts.length === 0 ? (
          <div className="text-center py-8 text-black/60 dark:text-white/60 text-sm">
            No unresolved alerts. Systems operating within normal parameters.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {alerts.slice(0, 6).map((a) => (
              <div
                key={a.id}
                className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 hover:border-black/20 dark:hover:border-white/20 transition flex flex-col justify-between space-y-3"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <RiskBadge level={a.risk_level} />
                    <span className="text-[10px] font-mono text-black/60 dark:text-white/60 uppercase bg-white dark:bg-black px-2 py-0.5 rounded border border-black/10 dark:border-white/10">
                      {a.status}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-black dark:text-white mt-2 line-clamp-2">
                    {a.description}
                  </h4>
                  <div className="text-xs text-black/60 dark:text-white/60 mt-1 font-mono">
                    Score: <span className="font-bold text-red-600 dark:text-red-400">{a.score.toFixed(3)}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-black/10 dark:border-white/10 text-[11px] text-black/60 dark:text-white/60">
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                  <Link
                    to={`/alerts`}
                    className="text-blue-600 dark:text-blue-400 hover:underline font-semibold"
                  >
                    Triage →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Transaction Details Modal */}
      {selectedTx && (
        <Modal
          isOpen={!!selectedTx}
          onClose={() => setSelectedTx(null)}
          title={`Transaction: ${selectedTx.transaction_ref}`}
          subtitle={`Evaluated at ${new Date(selectedTx.timestamp).toLocaleString()}`}
          maxWidth="4xl"
        >
          <div className="space-y-6">
            {/* Top Score & Decision Header */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10 flex flex-col justify-center items-center text-center">
                <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Automated Decision</span>
                <div className="mt-2">
                  <DecisionBadge
                    decision={selectedTx.prediction?.decision || selectedTx.decision || (selectedTx.is_fraud ? 'BLOCK' : 'ALLOW')}
                    size="lg"
                  />
                </div>
              </div>

              <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10 flex flex-col justify-center items-center text-center">
                <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Fraud Probability</span>
                <span className="text-2xl font-black text-black dark:text-white mt-1">
                  {((selectedTx.prediction?.fraud_score ?? selectedTx.fraud_score ?? 0) * 100).toFixed(1)}%
                </span>
                <RiskBadge level={selectedTx.prediction?.risk_level || selectedTx.risk_level || 'Low'} className="mt-1" />
              </div>

              <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10 flex flex-col justify-center items-center text-center">
                <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Transaction Amount</span>
                <span className="text-2xl font-black text-blue-600 dark:text-blue-400 mt-1">
                  ${selectedTx.amount.toFixed(2)}
                </span>
                <span className="text-xs text-black/60 dark:text-white/60 font-mono mt-0.5">{selectedTx.currency || 'USD'}</span>
              </div>
            </div>

            {/* Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-2">
                <h4 className="text-xs font-bold text-black/60 dark:text-white/60 uppercase">Entity Information</h4>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Merchant</span>
                    <span className="text-black dark:text-white font-medium">{selectedTx.merchant || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Category</span>
                    <span className="text-black dark:text-white font-medium">{selectedTx.category || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Country</span>
                    <span className="text-black dark:text-white font-medium">{selectedTx.country || 'US'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-black/60 dark:text-white/60">User ID</span>
                    <span className="text-black dark:text-white font-mono text-[11px]">{selectedTx.user_id || 'guest_user'}</span>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-2">
                <h4 className="text-xs font-bold text-black/60 dark:text-white/60 uppercase">Model Inference Stats</h4>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Model Version</span>
                    <span className="text-black dark:text-white font-mono">{selectedTx.prediction?.model_version || 'xgboost-v3.0.0'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Inference Latency</span>
                    <span className="text-blue-600 dark:text-blue-400 font-mono font-bold">
                      {selectedTx.prediction?.latency_ms ? `${selectedTx.prediction.latency_ms.toFixed(2)} ms` : '0.36 ms (C++ Booster)'}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">Inference Engine</span>
                    <span className="text-blue-600 dark:text-blue-400 font-semibold">XGBoost Native Booster / ONNX</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-black/60 dark:text-white/60">Action</span>
                    <Link
                      to={`/transactions/${selectedTx.id}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 font-semibold"
                    >
                      <span>Full 360° Inspector</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>

            {/* SHAP Chart if available */}
            {selectedTx.prediction?.shap_values && selectedTx.prediction.shap_values.length > 0 && (
              <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <h4 className="text-xs font-bold text-black/60 dark:text-white/60 uppercase mb-2">Top SHAP Feature Drivers</h4>
                <SHAPChart features={selectedTx.prediction.shap_values} />
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
