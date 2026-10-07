import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Bell,
  Clock,
  Filter,
  ExternalLink,
  ChevronRight,
  Eye,
  Radio,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import { alertService } from '../services/alert.service';
import { useRealtime } from '../context/RealtimeContext';
import { useTheme } from '../context/ThemeContext';
import { Alert, AlertStatus, RiskLevel } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { Modal } from '../components/common/Modal';
import { SHAPChart } from '../components/common/SHAPChart';

export const AlertsPage: React.FC = () => {
  const { subscribe, simulateEvent } = useRealtime();
  const { isDark } = useTheme();

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [riskFilter, setRiskFilter] = useState<string>('All');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [newlyArrivedAlertId, setNewlyArrivedAlertId] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const data = await alertService.getAlerts({
        limit: 150,
        status: statusFilter === 'All' ? undefined : (statusFilter as AlertStatus),
        risk_level: riskFilter === 'All' ? undefined : (riskFilter as RiskLevel),
      });
      setAlerts(data || []);
    } catch (err) {
      console.error('Error fetching alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, riskFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  // Real-Time Event Subscription for Security Alerts
  useEffect(() => {
    const unsub = subscribe('fraud_alert', (data: any) => {
      const newAlert: Alert = {
        id: data.id || `alt_${Date.now()}`,
        transaction_id: data.transaction_id,
        alert_type: data.alert_type || 'credit_fraud',
        risk_level: data.risk_level || 'High',
        score: Number(data.score || 0.9),
        description: data.description || 'Automated high risk alert triggered',
        status: data.status || 'open',
        created_at: data.created_at || new Date().toISOString(),
        shap_values: data.shap_values,
      };

      setNewlyArrivedAlertId(newAlert.id);
      setTimeout(() => setNewlyArrivedAlertId(null), 4000);

      setAlerts((prev) => [newAlert, ...prev]);
    });

    return () => {
      unsub();
    };
  }, [subscribe]);

  const handleStatusChange = async (alertId: string, newStatus: AlertStatus) => {
    try {
      setUpdatingId(alertId);
      const updated = await alertService.updateAlertStatus(alertId, newStatus);
      setAlerts((prev) => prev.map((a) => (a.id === alertId ? { ...a, ...updated } : a)));
      if (selectedAlert && selectedAlert.id === alertId) {
        setSelectedAlert({ ...selectedAlert, ...updated });
      }
    } catch (err) {
      console.error('Failed to update alert status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const highRiskCount = alerts.filter((a) => a.risk_level === 'High').length;
  const openCount = alerts.filter((a) => a.status === 'open').length;
  const avgScore =
    alerts.length > 0 ? alerts.reduce((acc, a) => acc + a.score, 0) / alerts.length : 0;

  // Timeline chart data aggregated by date
  const dateMap: Record<string, { date: string; High: number; Medium: number; Low: number }> = {};
  alerts.forEach((a) => {
    const d = new Date(a.created_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
    if (!dateMap[d]) {
      dateMap[d] = { date: d, High: 0, Medium: 0, Low: 0 };
    }
    const r = a.risk_level || 'Low';
    if (dateMap[d][r] !== undefined) {
      dateMap[d][r] += 1;
    }
  });
  const timelineData = Object.values(dateMap).reverse().slice(-14);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
            <Bell className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            Security Incident Alerts & Triage
          </h1>
          <p className="text-sm text-black/60 dark:text-white/60 mt-1">
            Real-time incident stream, SHAP driver analysis, and lifecycle resolution status
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => simulateEvent('fraud_alert')}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-red-600/10 border border-red-600/20 text-red-600 dark:text-red-400 hover:bg-red-600/20 transition shadow-sm cursor-pointer"
          >
            <Radio className="w-3.5 h-3.5 text-red-600 dark:text-red-400 animate-pulse" />
            <span>Simulate Fraud Alert</span>
          </button>

          <button
            onClick={fetchAlerts}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-black border border-black/10 dark:border-white/10 text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/5 transition shadow-sm cursor-pointer"
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Resync</span>
          </button>
        </div>
      </div>

      {/* KPI Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 shadow-sm transition-colors">
          <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Total Alerts</span>
          <div className="text-2xl font-bold text-black dark:text-white mt-1">{alerts.length}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 shadow-sm transition-colors">
          <span className="text-xs text-red-600 dark:text-red-400 uppercase font-semibold">High Risk Critical</span>
          <div className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">{highRiskCount}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 shadow-sm transition-colors">
          <span className="text-xs text-blue-600 dark:text-blue-400 uppercase font-semibold">Open / Actionable</span>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{openCount}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 shadow-sm transition-colors">
          <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Avg Anomaly Score</span>
          <div className="text-2xl font-bold text-black dark:text-white mt-1">{avgScore.toFixed(3)}</div>
        </div>
      </div>

      {/* Timeline Chart */}
      {timelineData.length > 0 && (
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm transition-colors">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-black dark:text-white">Alert Frequency Timeline</h3>
              <p className="text-xs text-black/60 dark:text-white/60">Trend of triggered risk events across days</p>
            </div>
          </div>
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timelineData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="date" stroke={isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)"} tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }} />
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
                <Area type="monotone" dataKey="High" stackId="1" stroke="#dc2626" fill="#dc2626" fillOpacity={0.4} />
                <Area type="monotone" dataKey="Medium" stackId="1" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
                <Area type="monotone" dataKey="Low" stackId="1" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm transition-colors">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-black/60 dark:text-white/60" />
            <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-lg px-3 py-1.5 text-xs text-black dark:text-white focus:outline-none focus:border-blue-600"
            >
              <option value="All">All Statuses</option>
              <option value="open">Open (Actionable)</option>
              <option value="reviewed">Reviewed (In Progress)</option>
              <option value="resolved">Resolved</option>
              <option value="false_positive">False Positive</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase">Risk Tier:</span>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-lg px-3 py-1.5 text-xs text-black dark:text-white focus:outline-none focus:border-blue-600"
            >
              <option value="All">All Risks</option>
              <option value="High">High Risk</option>
              <option value="Medium">Medium Risk</option>
              <option value="Low">Low Risk</option>
            </select>
          </div>
        </div>
      </div>

      {/* Alert Card List */}
      <div className="space-y-3">
        {loading && alerts.length === 0 ? (
          <LoadingSpinner text="Retrieving security alerts..." />
        ) : alerts.length === 0 ? (
          <EmptyState
            title="No alerts found"
            description="All incidents have been resolved or no events match the current filter criteria."
          />
        ) : (
          alerts.map((alert) => {
            const isUpdating = updatingId === alert.id;
            const isJustArrived = alert.id === newlyArrivedAlertId;

            return (
              <div
                key={alert.id}
                className={`border rounded-2xl p-5 shadow-sm transition-all duration-700 ${
                  isJustArrived
                    ? 'bg-red-600/10 border-red-600'
                    : 'bg-white dark:bg-black border-black/10 dark:border-white/10 hover:border-black/30 dark:hover:border-white/30'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <RiskBadge level={alert.risk_level} />
                      <span className="text-xs font-mono text-black/80 dark:text-white/80 bg-black/5 dark:bg-white/10 px-2.5 py-0.5 rounded-md border border-black/10 dark:border-white/10">
                        {alert.alert_type === 'credit_fraud' ? '💳 Credit Fraud' : '👤 Behavior Anomaly'}
                      </span>
                      <span className="text-xs font-mono text-black/40 dark:text-white/40">
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-black dark:text-white tracking-tight">
                      {alert.description}
                    </h3>
                    <div className="text-xs text-black/60 dark:text-white/60 flex flex-wrap items-center gap-4 pt-1">
                      <span>Score: <strong className="text-black dark:text-white">{alert.score.toFixed(4)}</strong></span>
                      {alert.transaction_id && (
                        <Link
                          to={`/transactions/${alert.transaction_id}`}
                          className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 font-semibold font-mono"
                        >
                          <span>Txn: {alert.transaction_id.slice(0, 8)}...</span>
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      )}
                      {alert.resolved_at && (
                        <span className="text-blue-600 dark:text-blue-400">Resolved at: {new Date(alert.resolved_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-3 self-end lg:self-center">
                    <button
                      onClick={() => setSelectedAlert(alert)}
                      className="px-3 py-1.5 rounded-xl bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20 text-black dark:text-white transition text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>

                    <select
                      value={alert.status}
                      disabled={isUpdating}
                      onChange={(e) => handleStatusChange(alert.id, e.target.value as AlertStatus)}
                      className={`bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-1.5 text-xs font-bold focus:outline-none focus:border-blue-600 ${
                        alert.status === 'open'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-blue-600 dark:text-blue-400'
                      }`}
                    >
                      <option value="open">Open</option>
                      <option value="reviewed">Reviewed</option>
                      <option value="resolved">Resolved</option>
                      <option value="false_positive">False Positive</option>
                    </select>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Alert Details Modal */}
      {selectedAlert && (
        <Modal
          isOpen={!!selectedAlert}
          onClose={() => setSelectedAlert(null)}
          title={`Alert: ${selectedAlert.alert_type.toUpperCase()}`}
          subtitle={`Triggered on ${new Date(selectedAlert.created_at).toLocaleString()}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 flex items-center justify-between">
              <div>
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-semibold">Incident Risk & Score</span>
                <div className="flex items-center gap-2 mt-1">
                  <RiskBadge level={selectedAlert.risk_level} />
                  <span className="text-base font-black text-black dark:text-white font-mono">{selectedAlert.score.toFixed(4)}</span>
                </div>
              </div>
              <div>
                <span className="text-black/60 dark:text-white/60 block text-[10px] uppercase font-semibold">Current Status</span>
                <span className="text-sm font-bold text-blue-600 dark:text-blue-400 uppercase mt-1 block">{selectedAlert.status}</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-2">
              <h4 className="font-bold text-black/80 dark:text-white/80 uppercase text-[10px]">Description & Rationale</h4>
              <p className="text-sm text-black dark:text-white">{selectedAlert.description}</p>
            </div>

            {selectedAlert.shap_values && selectedAlert.shap_values.length > 0 && (
              <div className="p-4 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                <h4 className="font-bold text-black/80 dark:text-white/80 uppercase text-[10px] mb-2">SHAP Driver Analysis</h4>
                <SHAPChart features={selectedAlert.shap_values} />
              </div>
            )}

            {selectedAlert.transaction_id && (
              <div className="pt-2 flex justify-end">
                <Link
                  to={`/transactions/${selectedAlert.transaction_id}`}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold inline-flex items-center gap-1.5"
                >
                  <span>Open Full 360° Transaction Inspector</span>
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
