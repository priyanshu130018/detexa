import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Download,
  CreditCard,
  RefreshCw,
  Zap,
  ChevronRight,
  Radio,
} from 'lucide-react';
import { transactionService } from '../services/transaction.service';
import { useRealtime } from '../context/RealtimeContext';
import { Transaction, RiskLevel } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';
import { DecisionBadge } from '../components/common/DecisionBadge';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { formatINR, formatIST, formatISTTime } from '../utils/formatters';

export const TransactionsPage: React.FC = () => {
  const navigate = useNavigate();
  const { connectionState, subscribe, simulateEvent } = useRealtime();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('All');
  const [decisionFilter, setDecisionFilter] = useState<string>('All');
  const [typeFilter, setTypeFilter] = useState<string>('All');
  const [limit, setLimit] = useState<number>(100);
  const [newlyArrivedTxId, setNewlyArrivedTxId] = useState<string | null>(null);

  const fetchTransactions = useCallback(async () => {
    try {
      setLoading(true);
      let isFraudParam: boolean | undefined = undefined;
      if (typeFilter === 'Fraud Only') isFraudParam = true;
      if (typeFilter === 'Legit Only') isFraudParam = false;

      const riskParam = riskFilter === 'All' ? undefined : (riskFilter as RiskLevel);

      const data = await transactionService.getTransactions({
        limit,
        is_fraud: isFraudParam,
        risk_level: riskParam,
        search: search.trim() || undefined,
      });

      setTransactions(data || []);
    } catch (err) {
      console.error('Error fetching transactions:', err);
    } finally {
      setLoading(false);
    }
  }, [limit, typeFilter, riskFilter, search]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  // Real-Time Event Subscription (Pure WebSocket/SSE - No Polling)
  useEffect(() => {
    const unsub = subscribe('new_transaction', (data: any) => {
      const newTx: Transaction = {
        id: data.id || data.transaction_id || `tx_${Date.now()}`,
        transaction_ref: data.transaction_ref || `TXN-${Date.now()}`,
        amount: Number(data.amount || 0),
        merchant: data.merchant,
        category: data.category,
        country: data.country || 'IN',
        state: data.state || 'Maharashtra',
        currency: data.currency || 'INR',
        fraud_score: Number(data.fraud_score || 0),
        risk_level: data.risk_level || 'Low',
        decision: data.decision || 'ALLOW',
        is_fraud: Boolean(data.is_fraud),
        timestamp: data.timestamp || new Date().toISOString(),
        prediction: {
          id: data.id,
          fraud_score: Number(data.fraud_score || 0),
          risk_level: data.risk_level || 'Low',
          decision: data.decision || 'ALLOW',
          latency_ms: data.latency_ms || 0.36,
          model_version: data.model_version || 'xgboost-v3.0.0',
        },
      };

      setNewlyArrivedTxId(newTx.id);
      setTimeout(() => setNewlyArrivedTxId(null), 3500);

      // Prepend to visible list
      setTransactions((prev) => [newTx, ...prev.slice(0, limit - 1)]);
    });

    return () => {
      unsub();
    };
  }, [subscribe, limit]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTransactions();
  };

  const handleExportCSV = () => {
    if (transactions.length === 0) return;
    const headers = [
      'ID',
      'Reference',
      'Amount',
      'Merchant',
      'Category',
      'Country',
      'FraudScore',
      'RiskLevel',
      'Decision',
      'Timestamp',
    ];
    const rows = transactions.map((t) => [
      t.id,
      t.transaction_ref,
      t.amount,
      t.merchant || '',
      t.category || '',
      t.country || '',
      t.prediction?.fraud_score ?? t.fraud_score ?? 0,
      t.prediction?.risk_level ?? t.risk_level ?? 'Low',
      t.prediction?.decision ?? t.decision ?? (t.is_fraud ? 'BLOCK' : 'ALLOW'),
      t.timestamp,
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `detexa_transactions_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Client-side filtering for decision if set
  const filteredTransactions = transactions.filter((t) => {
    if (decisionFilter === 'All') return true;
    const dec = t.prediction?.decision ?? t.decision ?? (t.is_fraud ? 'BLOCK' : 'ALLOW');
    return dec.toUpperCase() === decisionFilter.toUpperCase();
  });

  const totalFraud = filteredTransactions.filter((t) => t.is_fraud || t.decision === 'BLOCK').length;
  const avgAmount =
    filteredTransactions.length > 0
      ? filteredTransactions.reduce((acc, t) => acc + t.amount, 0) / filteredTransactions.length
      : 0;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
            <CreditCard className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            Live Transaction Stream & Ledger
          </h1>
          <p className="text-sm text-black/60 dark:text-white/60 mt-1">
            Real-time multi-threaded ingestion feed with automated decision scoring and entity inspection
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {connectionState === 'connected' ? (
            <span className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600/15 border border-blue-500/30 text-blue-600 dark:text-blue-400">
              <Zap className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 fill-blue-600 dark:fill-blue-400 animate-pulse" />
              <span>Stream: Connected (Live Push)</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-600 dark:text-blue-400" />
              <span>Stream: {connectionState}</span>
            </span>
          )}

          <button
            onClick={() => simulateEvent('new_transaction')}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20 transition shadow-sm cursor-pointer"
          >
            <Radio className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 animate-pulse" />
            <span>Simulate Incoming</span>
          </button>

          <button
            onClick={fetchTransactions}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-black border border-black/10 dark:border-white/10 text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/10 transition shadow-sm cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Resync</span>
          </button>

          <button
            onClick={handleExportCSV}
            disabled={filteredTransactions.length === 0}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition shadow-md shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-5 shadow-sm space-y-4 transition-colors">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
              Search Reference / Merchant
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-black/40 dark:text-white/40" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="e.g. TXN-1082 or Stripe"
                className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl pl-9 pr-4 py-2 text-xs text-black dark:text-white placeholder-black/30 dark:placeholder-white/30 focus:outline-none focus:border-blue-500 transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
              Decision Verdict
            </label>
            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-500 transition"
            >
              <option value="All">All Decisions</option>
              <option value="ALLOW">ALLOW (Clean)</option>
              <option value="CHALLENGE">CHALLENGE (Step-Up)</option>
              <option value="REVIEW">REVIEW (Manual)</option>
              <option value="BLOCK">BLOCK (Intercepted)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
              Risk Level
            </label>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-500 transition"
            >
              <option value="All">All Risk Levels</option>
              <option value="High">High Risk</option>
              <option value="Medium">Medium Risk</option>
              <option value="Low">Low Risk</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
              Classification
            </label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full bg-black/5 dark:bg-white/5 border border-black/15 dark:border-white/15 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-500 transition"
            >
              <option value="All">All Transactions</option>
              <option value="Fraud Only">Fraud / Flagged Only</option>
              <option value="Legit Only">Legitimate Only</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
              Batch Limit ({limit})
            </label>
            <input
              type="range"
              min="25"
              max="300"
              step="25"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-2"
            />
          </div>
        </form>

        {/* Metric Summary Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-black/10 dark:border-white/10 text-center">
          <div className="bg-black/5 dark:bg-white/5 p-2.5 rounded-xl border border-black/10 dark:border-white/10">
            <span className="text-[11px] text-black/60 dark:text-white/60 uppercase font-semibold">Total Visible</span>
            <div className="text-lg font-bold text-black dark:text-white mt-0.5">{filteredTransactions.length}</div>
          </div>
          <div className="bg-black/5 dark:bg-white/5 p-2.5 rounded-xl border border-black/10 dark:border-white/10">
            <span className="text-[11px] text-red-600 dark:text-red-400 uppercase font-semibold">Flagged / Blocked</span>
            <div className="text-lg font-bold text-red-600 dark:text-red-400 mt-0.5">{totalFraud}</div>
          </div>
          <div className="bg-black/5 dark:bg-white/5 p-2.5 rounded-xl border border-black/10 dark:border-white/10">
            <span className="text-[11px] text-black/60 dark:text-white/60 uppercase font-semibold">Incident Rate</span>
            <div className="text-lg font-bold text-black dark:text-white mt-0.5">
              {filteredTransactions.length > 0 ? ((totalFraud / filteredTransactions.length) * 100).toFixed(1) : 0}%
            </div>
          </div>
          <div className="bg-black/5 dark:bg-white/5 p-2.5 rounded-xl border border-black/10 dark:border-white/10">
            <span className="text-[11px] text-black/60 dark:text-white/60 uppercase font-semibold">Avg Ticket</span>
            <div className="text-lg font-bold text-black dark:text-white mt-0.5">{formatINR(avgAmount)}</div>
          </div>
        </div>
      </div>

      {/* Table Section */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl overflow-hidden shadow-sm transition-colors">
        {loading && transactions.length === 0 ? (
          <LoadingSpinner text="Connecting to real-time transaction stream..." />
        ) : filteredTransactions.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No transactions found"
              description="No transactions match your search or filter configuration. Waiting for live streaming events..."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm text-black dark:text-white">
              <thead className="text-[11px] uppercase tracking-wider bg-black/5 dark:bg-white/5 text-black/60 dark:text-white/60 border-b border-black/10 dark:border-white/10">
                <tr>
                  <th className="px-4 py-3.5">Reference</th>
                  <th className="px-4 py-3.5">Amount (INR)</th>
                  <th className="px-4 py-3.5">Merchant / Cat</th>
                  <th className="px-4 py-3.5">State / Location</th>
                  <th className="px-4 py-3.5">Fraud Score</th>
                  <th className="px-4 py-3.5">Risk Tier</th>
                  <th className="px-4 py-3.5">Verdict</th>
                  <th className="px-4 py-3.5">Time (IST)</th>
                  <th className="px-4 py-3.5 text-right">360° Inspector</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/10 dark:divide-white/10">
                {filteredTransactions.map((t) => {
                  const score = t.prediction?.fraud_score ?? t.fraud_score ?? 0;
                  const decision = t.prediction?.decision ?? t.decision ?? (t.is_fraud ? 'BLOCK' : 'ALLOW');
                  const riskLevel = t.prediction?.risk_level ?? t.risk_level ?? (score >= 0.75 ? 'High' : score >= 0.5 ? 'Medium' : 'Low');
                  const isJustArrived = t.id === newlyArrivedTxId;

                  return (
                    <tr
                      key={t.id}
                      onClick={() => navigate(`/transactions/${t.id}`)}
                      className={`cursor-pointer transition-all duration-700 group ${
                        isJustArrived
                          ? 'bg-blue-600/15 border-l-4 border-blue-500'
                          : 'hover:bg-black/5 dark:hover:bg-white/5'
                      }`}
                    >
                      <td className="px-4 py-3 font-mono text-xs font-bold text-blue-600 dark:text-blue-400 group-hover:underline">
                        {t.transaction_ref}
                      </td>
                      <td className="px-4 py-3 font-bold text-black dark:text-white">
                        {formatINR(t.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-black dark:text-white">{t.merchant || 'General Merchant'}</div>
                        <div className="text-[11px] text-black/60 dark:text-white/60">{t.category || 'eCommerce'}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-black/60 dark:text-white/60">
                        {t.state ? `${t.state}, IN` : (t.country || 'IN')}
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
                      <td className="px-4 py-3 text-xs text-black/60 dark:text-white/60 whitespace-nowrap font-mono">
                        {formatISTTime(t.timestamp)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 group-hover:underline">
                          <span>Inspect</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
