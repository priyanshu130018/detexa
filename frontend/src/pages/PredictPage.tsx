import React, { useState } from 'react';
import { SearchCode, CreditCard, UserCheck, Upload, Play, Shuffle } from 'lucide-react';
import { predictService } from '../services/predict.service';
import { BatchCreditFraudResult, BehaviorPredictionResult, FraudPredictionResult } from '../types';
import { ScoreGauge } from '../components/common/ScoreGauge';
import { SHAPChart } from '../components/common/SHAPChart';

export const PredictPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'credit' | 'batch' | 'behavior'>('credit');

  // Single Credit Form State
  const [amount, setAmount] = useState<number>(4500.0);
  const [merchant, setMerchant] = useState<string>('Reliance Digital');
  const [category, setCategory] = useState<string>('electronics');
  const [country, setCountry] = useState<string>('IN');
  const [vFeatures, setVFeatures] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {};
    for (let i = 1; i <= 28; i++) init[`v${i}`] = 0.0;
    return init;
  });
  const [creditResult, setCreditResult] = useState<FraudPredictionResult | null>(null);
  const [creditLoading, setCreditLoading] = useState(false);

  // Batch Credit Form State
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchResult, setBatchResult] = useState<BatchCreditFraudResult | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);

  // Behavior Form State
  const [sessionId, setSessionId] = useState<string>(() => Math.random().toString(36).substring(2, 12));
  const [ipAddress, setIpAddress] = useState<string>('103.21.124.5');
  const [loginHour, setLoginHour] = useState<number>(14);
  const [typingSpeed, setTypingSpeed] = useState<number>(4.8);
  const [mouseVelocity, setMouseVelocity] = useState<number>(180);
  const [isVpn, setIsVpn] = useState<boolean>(false);
  const [isTor, setIsTor] = useState<boolean>(false);
  const [failedLogins, setFailedLogins] = useState<number>(0);
  const [deviceChange, setDeviceChange] = useState<boolean>(false);
  const [behaviorResult, setBehaviorResult] = useState<BehaviorPredictionResult | null>(null);
  const [behaviorLoading, setBehaviorLoading] = useState(false);

  const handleSimulateFraudPattern = () => {
    const fraudV: Record<string, number> = {};
    for (let i = 1; i <= 28; i++) {
      // Skew typical fraud-sensitive PCA columns (V14, V4, V12, V10)
      if (i === 14) fraudV[`v${i}`] = -4.5;
      else if (i === 4) fraudV[`v${i}`] = 3.8;
      else if (i === 12) fraudV[`v${i}`] = -3.2;
      else if (i === 10) fraudV[`v${i}`] = -2.9;
      else fraudV[`v${i}`] = Number(((Math.random() - 0.5) * 4).toFixed(3));
    }
    setVFeatures(fraudV);
    setAmount(85000.0);
    setMerchant('Reliance Digital Mumbai');
  };

  const handleResetVFeatures = () => {
    const zeroV: Record<string, number> = {};
    for (let i = 1; i <= 28; i++) zeroV[`v${i}`] = 0.0;
    setVFeatures(zeroV);
    setAmount(4500.0);
  };

  const handleCreditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreditLoading(true);
      const payload = {
        amount,
        merchant,
        category,
        country,
        ...vFeatures,
      };
      const res = await predictService.predictCredit(payload);
      setCreditResult(res);
    } catch (err) {
      console.error('Credit prediction error:', err);
    } finally {
      setCreditLoading(false);
    }
  };

  const handleBehaviorSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setBehaviorLoading(true);
      const payload = {
        session_id: sessionId,
        ip_address: ipAddress,
        login_hour: loginHour,
        typing_speed: typingSpeed,
        mouse_velocity: mouseVelocity,
        is_vpn: isVpn,
        is_tor: isTor,
        failed_logins: failedLogins,
        device_change: deviceChange,
      };
      const res = await predictService.predictBehavior(payload);
      setBehaviorResult(res);
    } catch (err) {
      console.error('Behavior prediction error:', err);
    } finally {
      setBehaviorLoading(false);
    }
  };

  const handleBatchUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!batchFile) return;

    try {
      setBatchLoading(true);
      const text = await batchFile.text();
      const lines = text.split('\n').filter((l) => l.trim().length > 0);
      const headers = lines[0].split(',').map((h) => h.trim().toLowerCase());

      const txns: Record<string, any>[] = [];
      for (let i = 1; i < lines.length && i <= 100; i++) {
        const values = lines[i].split(',').map((v) => v.trim());
        const row: Record<string, any> = {};
        headers.forEach((h, idx) => {
          row[h] = isNaN(Number(values[idx])) ? values[idx] : Number(values[idx]);
        });
        if (row.amount === undefined && row.Amount !== undefined) row.amount = row.Amount;
        if (!row.amount) row.amount = 100.0;
        txns.push(row);
      }

      const res = await predictService.predictCreditBatch(txns);
      setBatchResult(res);
    } catch (err) {
      console.error('Batch scoring error:', err);
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
          <SearchCode className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          Live Prediction & Inference Console
        </h1>
        <p className="text-sm text-black/60 dark:text-white/60 mt-1">
          Perform live model inference with SHAP explanations or batch process transaction streams
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-black/10 dark:border-white/10 gap-2">
        <button
          onClick={() => setActiveTab('credit')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition cursor-pointer ${
            activeTab === 'credit'
              ? 'border-blue-600 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white'
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Single Transaction Scoring</span>
        </button>

        <button
          onClick={() => setActiveTab('batch')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition cursor-pointer ${
            activeTab === 'batch'
              ? 'border-blue-600 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white'
          }`}
        >
          <Upload className="w-4 h-4" />
          <span>Batch CSV Scoring</span>
        </button>

        <button
          onClick={() => setActiveTab('behavior')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition cursor-pointer ${
            activeTab === 'behavior'
              ? 'border-blue-600 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          <span>Behavioral Anomaly Detector</span>
        </button>
      </div>

      {/* ── TAB 1: Single Credit Transaction Scoring ── */}
      {activeTab === 'credit' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-4">
              <h2 className="text-base font-bold text-black dark:text-white">Transaction Parameters</h2>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSimulateFraudPattern}
                  className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-red-600 dark:text-red-400 bg-red-600/10 hover:bg-red-600/20 border border-red-600/30 rounded-lg transition cursor-pointer"
                >
                  <Shuffle className="w-3.5 h-3.5" />
                  <span>Simulate Fraud</span>
                </button>
                <button
                  type="button"
                  onClick={handleResetVFeatures}
                  className="px-3 py-1 text-xs font-semibold text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white bg-black/5 dark:bg-white/10 rounded-lg transition cursor-pointer"
                >
                  Reset V's
                </button>
              </div>
            </div>

            <form onSubmit={handleCreditSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Amount (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={amount}
                    onChange={(e) => setAmount(Number(e.target.value))}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Merchant Name
                  </label>
                  <input
                    type="text"
                    value={merchant}
                    onChange={(e) => setMerchant(e.target.value)}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                  >
                    <option value="electronics">Electronics</option>
                    <option value="food">Food & Dining</option>
                    <option value="grocery">Groceries</option>
                    <option value="travel">Travel & Transport</option>
                    <option value="entertainment">Entertainment</option>
                    <option value="clothing">Clothing & Apparel</option>
                    <option value="services">Utilities & Services</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Country
                  </label>
                  <select
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                  >
                    <option value="IN">India (IN)</option>
                    <option value="US">United States (US)</option>
                    <option value="GB">United Kingdom (GB)</option>
                    <option value="SG">Singapore (SG)</option>
                    <option value="AE">United Arab Emirates (AE)</option>
                  </select>
                </div>
              </div>

              {/* Collapsible PCA V-features grid */}
              <div className="pt-2">
                <label className="block text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider mb-2">
                  PCA Feature Components (V1 – V28)
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2 max-h-48 overflow-y-auto p-2 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10">
                  {Array.from({ length: 28 }, (_, i) => i + 1).map((idx) => (
                    <div key={`v${idx}`} className="text-center">
                      <span className="text-[10px] text-black/40 dark:text-white/40 font-mono">V{idx}</span>
                      <input
                        type="number"
                        step="0.01"
                        value={vFeatures[`v${idx}`] || 0}
                        onChange={(e) =>
                          setVFeatures((prev) => ({
                            ...prev,
                            [`v${idx}`]: Number(e.target.value),
                          }))
                        }
                        className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded px-1.5 py-0.5 text-xs text-center text-black dark:text-white focus:outline-none focus:border-blue-600"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={creditLoading}
                className="w-full py-3 px-4 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-lg transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {creditLoading ? (
                  <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Run Fraud Classification</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-5 space-y-6">
            {creditResult ? (
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-6 animate-fadeIn">
                <ScoreGauge
                  score={creditResult.fraud_score}
                  label="Inference Score"
                  riskLevel={creditResult.risk_level}
                />

                <div className="bg-black/5 dark:bg-white/5 rounded-xl p-4 border border-black/10 dark:border-white/10 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Transaction Ref:</span>
                    <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{creditResult.transaction_ref || creditResult.transaction_id.slice(0, 10)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Fraud Flag:</span>
                    <span className={`font-bold ${creditResult.is_fraud ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {creditResult.is_fraud ? '🔴 POSITIVE (FRAUD)' : '🔵 NEGATIVE (LEGITIMATE)'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Model Version:</span>
                    <span className="text-black dark:text-white">{creditResult.model_version}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Latency:</span>
                    <span className="text-blue-600 dark:text-blue-400 font-mono">{creditResult.latency_ms.toFixed(1)} ms</span>
                  </div>
                </div>

                {/* SHAP Feature Explanations */}
                <div>
                  <h3 className="text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider mb-2">
                    Top SHAP Feature Contributions
                  </h3>
                  <SHAPChart features={creditResult.shap_top_features} />
                </div>
              </div>
            ) : (
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-12 text-center text-black/40 dark:text-white/40 shadow-sm">
                Configure transaction parameters and click <strong>Run Fraud Classification</strong> to see real-time probability and SHAP explainability.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 2: Batch CSV Scoring ── */}
      {activeTab === 'batch' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm max-w-2xl mx-auto space-y-4">
            <h2 className="text-base font-bold text-black dark:text-white">Upload Transaction Batch CSV</h2>
            <p className="text-xs text-black/60 dark:text-white/60">
              Upload a CSV file containing transactions (columns: Amount/amount, V1..V28). The ML engine will score all records in parallel.
            </p>

            <form onSubmit={handleBatchUpload} className="space-y-4">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setBatchFile(e.target.files ? e.target.files[0] : null)}
                className="block w-full text-xs text-black/60 dark:text-white/60 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer bg-black/5 dark:bg-white/5 p-2 rounded-xl border border-black/10 dark:border-white/10"
              />

              <button
                type="submit"
                disabled={!batchFile || batchLoading}
                className="w-full py-3 px-4 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-lg transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {batchLoading ? (
                  <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    <span>Score Batch Dataset</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {batchResult && (
            <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10">
                  <span className="text-xs text-black/60 dark:text-white/60 uppercase font-semibold">Total Processed</span>
                  <div className="text-2xl font-bold text-black dark:text-white mt-1">{batchResult.total_processed}</div>
                </div>
                <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10">
                  <span className="text-xs text-red-600 dark:text-red-400 uppercase font-semibold">Fraud Flagged</span>
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">{batchResult.fraud_detected_count}</div>
                </div>
                <div className="bg-black/5 dark:bg-white/5 p-4 rounded-xl border border-black/10 dark:border-white/10">
                  <span className="text-xs text-blue-600 dark:text-blue-400 uppercase font-semibold">Batch Latency</span>
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{batchResult.batch_latency_ms.toFixed(1)} ms</div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-black dark:text-white">
                  <thead className="bg-black/5 dark:bg-white/5 uppercase text-black/60 dark:text-white/60 border-b border-black/10 dark:border-white/10">
                    <tr>
                      <th className="px-4 py-2.5">Txn Reference</th>
                      <th className="px-4 py-2.5">Fraud Score</th>
                      <th className="px-4 py-2.5">Risk Level</th>
                      <th className="px-4 py-2.5">Classification</th>
                      <th className="px-4 py-2.5">Latency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-black/10 dark:divide-white/10">
                    {batchResult.predictions.map((p, idx) => (
                      <tr key={idx} className={p.is_fraud ? 'bg-red-600/10' : ''}>
                        <td className="px-4 py-2.5 font-mono text-blue-600 dark:text-blue-400">{p.transaction_ref || p.transaction_id.slice(0, 10)}</td>
                        <td className="px-4 py-2.5 font-mono font-bold text-black dark:text-white">{p.fraud_score.toFixed(4)}</td>
                        <td className="px-4 py-2.5 font-semibold">{p.risk_level}</td>
                        <td className="px-4 py-2.5 font-bold">
                          {p.is_fraud ? <span className="text-red-600 dark:text-red-400">FRAUD</span> : <span className="text-blue-600 dark:text-blue-400">LEGITIMATE</span>}
                        </td>
                        <td className="px-4 py-2.5 text-black/60 dark:text-white/60 font-mono">{p.latency_ms.toFixed(1)}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: Behavioral Anomaly Detector ── */}
      {activeTab === 'behavior' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-6">
            <h2 className="text-base font-bold text-black dark:text-white border-b border-black/10 dark:border-white/10 pb-4">
              Session Telemetry Parameters
            </h2>

            <form onSubmit={handleBehaviorSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Session Identifier
                  </label>
                  <input
                    type="text"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    IP Address
                  </label>
                  <input
                    type="text"
                    value={ipAddress}
                    onChange={(e) => setIpAddress(e.target.value)}
                    className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-sm text-black dark:text-white focus:outline-none focus:border-blue-600"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Login Hour ({loginHour}:00)
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="23"
                    value={loginHour}
                    onChange={(e) => setLoginHour(Number(e.target.value))}
                    className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-3"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Failed Logins ({failedLogins})
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="6"
                    value={failedLogins}
                    onChange={(e) => setFailedLogins(Number(e.target.value))}
                    className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-3"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Typing Speed: {typingSpeed} chars/sec
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="15"
                    step="0.5"
                    value={typingSpeed}
                    onChange={(e) => setTypingSpeed(Number(e.target.value))}
                    className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-3"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-1.5">
                    Mouse Velocity: {mouseVelocity} px/sec
                  </label>
                  <input
                    type="range"
                    min="20"
                    max="500"
                    step="10"
                    value={mouseVelocity}
                    onChange={(e) => setMouseVelocity(Number(e.target.value))}
                    className="w-full h-2 bg-black/10 dark:bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-3"
                  />
                </div>
              </div>

              {/* Flag Checkboxes */}
              <div className="grid grid-cols-3 gap-3 p-3 bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10">
                <label className="flex items-center gap-2 text-xs font-semibold text-black dark:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isVpn}
                    onChange={(e) => setIsVpn(e.target.checked)}
                    className="rounded border-black/20 dark:border-white/20 text-blue-600 focus:ring-0"
                  />
                  <span>VPN Active</span>
                </label>

                <label className="flex items-center gap-2 text-xs font-semibold text-black dark:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isTor}
                    onChange={(e) => setIsTor(e.target.checked)}
                    className="rounded border-black/20 dark:border-white/20 text-red-600 focus:ring-0"
                  />
                  <span>TOR Active</span>
                </label>

                <label className="flex items-center gap-2 text-xs font-semibold text-black dark:text-white cursor-pointer">
                  <input
                    type="checkbox"
                    checked={deviceChange}
                    onChange={(e) => setDeviceChange(e.target.checked)}
                    className="rounded border-black/20 dark:border-white/20 text-blue-600 focus:ring-0"
                  />
                  <span>Device Changed</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={behaviorLoading}
                className="w-full py-3 px-4 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-lg transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {behaviorLoading ? (
                  <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Run Anomaly Detection</span>
                  </>
                )}
              </button>
            </form>
          </div>

          <div className="lg:col-span-5 space-y-6">
            {behaviorResult ? (
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-6 animate-fadeIn">
                <ScoreGauge
                  score={behaviorResult.anomaly_score}
                  label="Session Anomaly Score"
                  riskLevel={behaviorResult.risk_level}
                />

                <div className="bg-black/5 dark:bg-white/5 rounded-xl p-4 border border-black/10 dark:border-white/10 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Session ID:</span>
                    <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{behaviorResult.session_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Anomaly State:</span>
                    <span className={`font-bold ${behaviorResult.is_anomalous ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {behaviorResult.is_anomalous ? '🚨 ANOMALOUS' : '🔵 NORMAL'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-black/60 dark:text-white/60">Latency:</span>
                    <span className="text-blue-600 dark:text-blue-400 font-mono">{behaviorResult.latency_ms.toFixed(1)} ms</span>
                  </div>
                </div>

                {behaviorResult.risk_factors.length > 0 && (
                  <div className="p-4 rounded-xl bg-red-600/10 border border-red-600/20 space-y-2">
                    <span className="text-xs font-bold text-red-600 dark:text-red-400 uppercase tracking-wider block">
                      Detected Risk Indicators
                    </span>
                    <ul className="space-y-1 text-xs text-red-600 dark:text-red-300">
                      {behaviorResult.risk_factors.map((f, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-600 dark:bg-red-400" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-12 text-center text-black/40 dark:text-white/40 shadow-sm">
                Set session telemetry and click <strong>Run Anomaly Detection</strong> to evaluate behavioral signals with Isolation Forest.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
