import React, { useEffect, useState } from 'react';
import { UserCheck } from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Legend,
} from 'recharts';
import { behaviorService } from '../services/behavior.service';
import { BehaviorLog, BehaviorStats } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { useTheme } from '../context/ThemeContext';

export const BehaviorPage: React.FC = () => {
  const { isDark } = useTheme();
  const [logs, setLogs] = useState<BehaviorLog[]>([]);
  const [stats, setStats] = useState<BehaviorStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [logsData, statsData] = await Promise.all([
        behaviorService.listBehaviorLogs(150),
        behaviorService.getBehaviorStats(),
      ]);
      setLogs(logsData);
      setStats(statsData);
    } catch (err) {
      console.error('Error fetching behavior telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return <LoadingSpinner size="lg" text="Analyzing behavioral telemetry..." />;
  }

  // Country aggregations
  const countryMap: Record<string, { country: string; total: number; vpn: number }> = {};
  logs.forEach((l) => {
    const c = l.geo_country || 'Unknown';
    if (!countryMap[c]) countryMap[c] = { country: c, total: 0, vpn: 0 };
    countryMap[c].total += 1;
    if (l.is_vpn || l.is_tor) countryMap[c].vpn += 1;
  });
  const countryData = Object.values(countryMap).slice(0, 8);

  const pieData = [
    { name: 'High Risk', value: stats?.high_risk_sessions || 0, color: '#dc2626' },
    { name: 'Medium Risk', value: stats?.medium_risk_sessions || 0, color: '#2563eb' },
    { name: 'Low Risk', value: stats?.low_risk_sessions || 0, color: '#3b82f6' },
  ];

  const tooltipContentStyle = {
    backgroundColor: isDark ? '#000000' : '#ffffff',
    borderColor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)',
    borderRadius: '8px',
    color: isDark ? '#ffffff' : '#000000',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
          <UserCheck className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          Behavioral Anomaly Telemetry
        </h1>
        <p className="text-sm text-black/60 dark:text-white/60 mt-1">
          Machine learning telemetry evaluating session dynamics, typing velocities, VPN/TOR flags, and device changes
        </p>
      </div>

      {/* KPI Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Total Sessions</span>
          <div className="text-2xl font-bold text-black dark:text-white mt-1">{stats?.total_sessions || logs.length}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-red-600 dark:text-red-400 uppercase font-semibold">High Risk Sessions</span>
          <div className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">{stats?.high_risk_sessions || 0}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-blue-600 dark:text-blue-400 uppercase font-semibold">Medium Risk</span>
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{stats?.medium_risk_sessions || 0}</div>
        </div>
        <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Avg Anomaly Score</span>
          <div className="text-2xl font-bold text-black dark:text-white mt-1">{(stats?.average_anomaly_score || 0).toFixed(3)}</div>
        </div>
      </div>

      {/* Visualizations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Country Telemetry Chart */}
        <div className="lg:col-span-8 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm">
          <h3 className="text-base font-bold text-black dark:text-white mb-1">Sessions by Country</h3>
          <p className="text-xs text-black/60 dark:text-white/60 mb-4">Total sessions vs VPN/TOR proxy usage</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={countryData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="country" stroke={isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)"} tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }} />
                <YAxis stroke={isDark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.4)"} tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }} />
                <Tooltip contentStyle={tooltipContentStyle} />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="total" name="Total Sessions" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="vpn" name="VPN / TOR Proxy" fill="#dc2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk Donut Chart */}
        <div className="lg:col-span-4 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-black dark:text-white">Session Risk Distribution</h3>
            <p className="text-xs text-black/60 dark:text-white/60">Isolation Forest classification breakdown</p>
          </div>
          <div className="h-56 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipContentStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center pt-2 border-t border-black/10 dark:border-white/10">
            {pieData.map((p) => (
              <div key={p.name}>
                <div className="text-[11px] font-semibold text-black/60 dark:text-white/60">{p.name}</div>
                <div className="text-sm font-bold text-black dark:text-white mt-0.5">{p.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Raw Behavior Logs Table */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm">
        <h3 className="text-base font-bold text-black dark:text-white mb-1">📋 Raw Session Activity Logs</h3>
        <p className="text-xs text-black/60 dark:text-white/60 mb-4">Granular telemetry captured across login sessions</p>

        {logs.length === 0 ? (
          <div className="text-center py-8 text-black/40 dark:text-white/40 text-sm">
            No behavioral logs recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-black dark:text-white">
              <thead className="bg-black/5 dark:bg-white/5 uppercase text-black/60 dark:text-white/60 border-b border-black/10 dark:border-white/10">
                <tr>
                  <th className="px-4 py-3">Session Ref</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">IP Address</th>
                  <th className="px-4 py-3">Login Hour</th>
                  <th className="px-4 py-3">Signals</th>
                  <th className="px-4 py-3">Typing Spd</th>
                  <th className="px-4 py-3">Anomaly Score</th>
                  <th className="px-4 py-3">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/10 dark:divide-white/10">
                {logs.map((l) => (
                  <tr key={l.id} className="hover:bg-black/5 dark:hover:bg-white/5 transition">
                    <td className="px-4 py-3 font-mono text-blue-600 dark:text-blue-400">{l.session_id}</td>
                    <td className="px-4 py-3 font-medium text-black dark:text-white">{l.geo_city ? `${l.geo_city}, ${l.geo_country}` : l.geo_country || 'US'}</td>
                    <td className="px-4 py-3 font-mono text-black/60 dark:text-white/60">{l.ip_address || '—'}</td>
                    <td className="px-4 py-3 text-black/80 dark:text-white/80">{l.login_hour !== undefined ? `${l.login_hour}:00` : '—'}</td>
                    <td className="px-4 py-3 space-x-1">
                      {l.is_tor && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-600/10 text-red-600 dark:text-red-400 border border-red-600/30">TOR</span>}
                      {l.is_vpn && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-600/30">VPN</span>}
                      {l.device_change && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-600/30">DEVICE</span>}
                      {!l.is_tor && !l.is_vpn && !l.device_change && <span className="text-black/40 dark:text-white/40 text-xs">Standard</span>}
                    </td>
                    <td className="px-4 py-3 font-mono text-black/80 dark:text-white/80">{l.typing_speed ? `${l.typing_speed} c/s` : '—'}</td>
                    <td className="px-4 py-3 font-mono font-bold text-black dark:text-white">
                      {l.anomaly_score !== undefined && l.anomaly_score !== null ? l.anomaly_score.toFixed(3) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge level={l.risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
