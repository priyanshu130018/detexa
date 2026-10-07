import React from 'react';
import { Link } from 'react-router-dom';
import { Zap, ArrowRight } from 'lucide-react';

export const LandingPage: React.FC = () => {
  return (
    <div className="space-y-16 py-8 md:py-16">
      {/* Hero Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/30">
            <Zap className="w-3.5 h-3.5" />
            Next-Gen AI Fraud Prevention Platform
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-black dark:text-white tracking-tight leading-tight">
            Protect your business from{' '}
            <span className="text-blue-600 dark:text-blue-400">
              financial fraud.
            </span>
          </h1>

          <p className="text-lg text-black/70 dark:text-white/70 max-w-2xl leading-relaxed">
            Real-time credit card fraud scoring and behavioral anomaly detection,
            powered by XGBoost, Isolation Forests, and SHAP explainability.
          </p>

          <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4 pt-2">
            <Link
              to="/register"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-600/25 hover:shadow-blue-600/40 transition"
            >
              <span>Get Started Free</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/10 bg-white dark:bg-black border border-black/15 dark:border-white/15 shadow-sm transition"
            >
              <span>Sign In to Dashboard</span>
            </Link>
          </div>

          {/* Feature Pills */}
          <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2 pt-4">
            {['⚡ Real-Time Scoring', '🤖 XGBoost Classifier', '👤 Behavioral Anomaly', '📊 SHAP Explainability'].map(
              (pill) => (
                <span
                  key={pill}
                  className="px-3 py-1 rounded-lg text-xs font-medium bg-black/5 dark:bg-white/5 text-black/80 dark:text-white/80 border border-black/10 dark:border-white/10 shadow-sm"
                >
                  {pill}
                </span>
              )
            )}
          </div>
        </div>

        {/* Hero Metric Cards */}
        <div className="lg:col-span-5 grid grid-cols-2 gap-4">
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 text-center space-y-2 shadow-sm">
            <div className="text-3xl lg:text-4xl font-extrabold text-blue-600 dark:text-blue-400">97.7%</div>
            <div className="text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider">AUC-ROC Accuracy</div>
            <div className="text-[11px] text-black/40 dark:text-white/40">Kaggle benchmark data</div>
          </div>
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 text-center space-y-2 shadow-sm">
            <div className="text-3xl lg:text-4xl font-extrabold text-blue-600 dark:text-blue-400">&lt; 35ms</div>
            <div className="text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider">Inference Latency</div>
            <div className="text-[11px] text-black/40 dark:text-white/40">Sub-second evaluation</div>
          </div>
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 text-center space-y-2 shadow-sm">
            <div className="text-3xl lg:text-4xl font-extrabold text-blue-600 dark:text-blue-400">2 ML</div>
            <div className="text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider">Detection Models</div>
            <div className="text-[11px] text-black/40 dark:text-white/40">Supervised & Unsupervised</div>
          </div>
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 text-center space-y-2 shadow-sm">
            <div className="text-3xl lg:text-4xl font-extrabold text-blue-600 dark:text-blue-400">REST</div>
            <div className="text-xs font-bold text-black/60 dark:text-white/60 uppercase tracking-wider">Integration</div>
            <div className="text-[11px] text-black/40 dark:text-white/40">FastAPI Gateway</div>
          </div>
        </div>
      </div>

      {/* How Detexa Works */}
      <div className="pt-8 border-t border-black/10 dark:border-white/10">
        <div className="text-center space-y-3 mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-black dark:text-white">
            How Detexa Protects Your Financial Infrastructure
          </h2>
          <p className="text-black/60 dark:text-white/60 text-sm max-w-xl mx-auto">
            A comprehensive, layered security intelligence pipeline that identifies suspicious card transactions and abnormal session behaviors.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-lg">
              01
            </div>
            <h3 className="text-lg font-bold text-black dark:text-white">Credit Card Fraud Scoring</h3>
            <p className="text-sm text-black/60 dark:text-white/60 leading-relaxed">
              XGBoost models evaluate 28 PCA-transformed features and engineered interaction metrics to output accurate fraud probability.
            </p>
          </div>

          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-lg">
              02
            </div>
            <h3 className="text-lg font-bold text-black dark:text-white">Behavioral Anomaly Engine</h3>
            <p className="text-sm text-black/60 dark:text-white/60 leading-relaxed">
              Isolation Forest analyzes user telemetry—TOR/VPN signals, typing speed, and off-hour access—to uncover hijacked accounts.
            </p>
          </div>

          <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-blue-600/10 border border-blue-500/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-lg">
              03
            </div>
            <h3 className="text-lg font-bold text-black dark:text-white">SHAP Explainability & Triage</h3>
            <p className="text-sm text-black/60 dark:text-white/60 leading-relaxed">
              Security analysts get transparent, feature-level SHAP explanations and actionable triage workflows to resolve alerts promptly.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
