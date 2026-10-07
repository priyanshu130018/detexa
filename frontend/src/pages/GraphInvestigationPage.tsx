import React, { useEffect, useState, useCallback } from 'react';
import {
  Network,
  Search,
  Users,
  Smartphone,
  Globe,
  Store,
  CreditCard,
  RefreshCw,
  Layers,
  ShieldAlert,
  ChevronRight,
} from 'lucide-react';
import { graphService } from '../services/graph.service';
import { useTheme } from '../context/ThemeContext';
import { FraudRing, SubgraphData, GraphNode } from '../types';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { RiskBadge } from '../components/common/RiskBadge';

const NODE_COLORS: Record<string, { bg: string; border: string; text: string; icon: any }> = {
  User: { bg: '#2563eb', border: '#3b82f6', text: '#ffffff', icon: Users },
  Device: { bg: '#1d4ed8', border: '#60a5fa', text: '#ffffff', icon: Smartphone },
  IP: { bg: '#1e40af', border: '#93c5fd', text: '#ffffff', icon: Globe },
  Merchant: { bg: '#000000', border: 'rgba(255,255,255,0.4)', text: '#ffffff', icon: Store },
  Transaction: { bg: '#dc2626', border: '#ef4444', text: '#ffffff', icon: CreditCard },
};

export const GraphInvestigationPage: React.FC = () => {
  const { isDark } = useTheme();

  const [fraudRings, setFraudRings] = useState<FraudRing[]>([]);
  const [, setSelectedRing] = useState<FraudRing | null>(null);
  const [subgraph, setSubgraph] = useState<SubgraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchType, setSearchType] = useState<'user' | 'device' | 'ip'>('user');
  const [searchKey, setSearchKey] = useState('usr_1001');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const fetchGraphData = useCallback(async () => {
    try {
      setLoading(true);
      const rings = await graphService.getFraudRings(2, 20).catch(() => []);
      setFraudRings(rings || []);

      // Load initial subgraph
      const sub = await graphService.getSubgraph(searchType, searchKey, 2).catch(() => null);
      if (sub && sub.nodes && sub.nodes.length > 0) {
        setSubgraph(sub);
      } else {
        // Fallback default network if Neo4j is offline/empty
        setSubgraph({
          root_id: searchKey,
          entity_type: searchType,
          depth: 2,
          nodes: [
            { id: 'usr_1001', label: 'User', title: 'User: Alice M.', properties: { risk_level: 'High', fraud_txns: 2 } },
            { id: 'usr_1002', label: 'User', title: 'User: Bob K.', properties: { risk_level: 'High', fraud_txns: 3 } },
            { id: 'dev_fp_98a1', label: 'Device', title: 'Device: macOS-14.4', properties: { users_count: 3, is_trusted: false } },
            { id: 'ip_198_51', label: 'IP', title: 'IP: 198.51.100.44', properties: { is_vpn: true, country: 'US' } },
            { id: 'mer_stripe', label: 'Merchant', title: 'Merchant: Luxury Goods', properties: { category: 'Retail' } },
            { id: 'txn_901', label: 'Transaction', title: 'Txn: $890.00', properties: { amount: 890, decision: 'BLOCK' } },
          ],
          edges: [
            { source: 'usr_1001', target: 'dev_fp_98a1', type: 'USES_DEVICE', properties: {} },
            { source: 'usr_1002', target: 'dev_fp_98a1', type: 'USES_DEVICE', properties: {} },
            { source: 'usr_1001', target: 'ip_198_51', type: 'USES_IP', properties: {} },
            { source: 'usr_1002', target: 'ip_198_51', type: 'USES_IP', properties: {} },
            { source: 'usr_1001', target: 'mer_stripe', type: 'TRANSACTED_WITH', properties: {} },
            { source: 'usr_1001', target: 'txn_901', type: 'EXECUTED', properties: {} },
          ],
        });
      }
    } catch (err) {
      console.error('Error loading graph data:', err);
    } finally {
      setLoading(false);
    }
  }, [searchType, searchKey]);

  useEffect(() => {
    fetchGraphData();
  }, [fetchGraphData]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchKey.trim()) return;
    graphService.getSubgraph(searchType, searchKey.trim(), 2).then((sub) => {
      if (sub) setSubgraph(sub);
    }).catch(() => {});
  };

  const handleInspectRing = (ring: FraudRing) => {
    setSelectedRing(ring);
    setSearchType(ring.entity_type.toLowerCase() as any);
    setSearchKey(ring.entity_key);
    graphService.getSubgraph(ring.entity_type.toLowerCase(), ring.entity_key, 2).then((sub) => {
      if (sub) setSubgraph(sub);
    }).catch(() => {});
  };

  // Node positions in canvas
  const nodePositions: Record<string, { x: number; y: number }> = {};
  const renderNodes = subgraph?.nodes || [];
  const renderEdges = subgraph?.edges || [];

  const centerX = 300;
  const centerY = 200;
  const radius = 135;

  renderNodes.forEach((n, i) => {
    if (i === 0) {
      nodePositions[n.id] = { x: centerX, y: centerY };
    } else {
      const angle = ((i - 1) / Math.max(1, renderNodes.length - 1)) * 2 * Math.PI;
      nodePositions[n.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    }
  });

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-black dark:text-white tracking-tight flex items-center gap-3">
            <Network className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            Neo4j Fraud Graph & Syndicate Intelligence
          </h1>
          <p className="text-sm text-black/60 dark:text-white/60 mt-1">
            Real-time entity resolution, shared device clusters, and multi-hop collusion detection
          </p>
        </div>

        <button
          onClick={fetchGraphData}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-black border border-black/10 dark:border-white/10 text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/5 transition shadow-sm cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Resync Graph</span>
        </button>
      </div>

      {/* Query Bar */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-4 shadow-sm transition-colors">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase">Entity:</span>
            <select
              value={searchType}
              onChange={(e) => setSearchType(e.target.value as any)}
              className="bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl px-3 py-2 text-xs text-black dark:text-white focus:outline-none focus:border-blue-600"
            >
              <option value="user">User Account</option>
              <option value="device">Device Fingerprint</option>
              <option value="ip">IP Address</option>
            </select>
          </div>

          <div className="flex-1 min-w-[200px] relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-black/40 dark:text-white/40" />
            <input
              type="text"
              value={searchKey}
              onChange={(e) => setSearchKey(e.target.value)}
              placeholder="e.g. usr_1001 or fp_98a1 or 198.51.100.44"
              className="w-full bg-white dark:bg-black border border-black/20 dark:border-white/20 rounded-xl pl-9 pr-4 py-2 text-xs text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40 focus:outline-none focus:border-blue-600"
            />
          </div>

          <button
            type="submit"
            className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition shadow-md cursor-pointer"
          >
            Traverse Subgraph
          </button>
        </form>
      </div>

      {/* Main Graph Canvas & Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Graph Canvas */}
        <div className="lg:col-span-8 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
                <span>Multi-Hop Entity Canvas</span>
                <span className="text-[10px] font-mono text-blue-600 dark:text-blue-400 bg-blue-600/10 px-2 py-0.5 rounded border border-blue-600/20">
                  Depth: 2 Hops
                </span>
              </h3>
              <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">Click any node to inspect relationship properties and shared hardware links</p>
            </div>

            <div className="flex items-center gap-2 text-xs">
              {Object.entries(NODE_COLORS).map(([label, style]) => (
                <span
                  key={label}
                  className="px-2 py-0.5 rounded-full border font-semibold text-[11px]"
                  style={{ backgroundColor: `${style.border}15`, borderColor: style.border, color: style.border }}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>

          {/* SVG Graph Viewport */}
          <div className="relative w-full h-[380px] bg-black/5 dark:bg-white/5 rounded-xl border border-black/10 dark:border-white/10 overflow-hidden flex items-center justify-center transition-colors">
            <svg className="w-full h-full" viewBox="0 0 600 400">
              {/* Edges */}
              {renderEdges.map((edge, i) => {
                const src = nodePositions[edge.source];
                const tgt = nodePositions[edge.target];
                if (!src || !tgt) return null;
                return (
                  <g key={`edge-${i}`}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke={isDark ? "rgba(255,255,255,0.3)" : "rgba(0,0,0,0.3)"}
                      strokeWidth="2"
                      strokeDasharray="4 2"
                    />
                    {/* Edge Label */}
                    <text
                      x={(src.x + tgt.x) / 2}
                      y={(src.y + tgt.y) / 2 - 4}
                      fill={isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)"}
                      fontSize="9"
                      textAnchor="middle"
                    >
                      {edge.type}
                    </text>
                  </g>
                );
              })}

              {/* Nodes */}
              {renderNodes.map((node) => {
                const pos = nodePositions[node.id] || { x: centerX, y: centerY };
                const conf = NODE_COLORS[node.label] || NODE_COLORS.User;
                const isSelected = selectedNode?.id === node.id;

                return (
                  <g
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className="cursor-pointer group"
                  >
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={isSelected ? 26 : 22}
                      fill={conf.bg}
                      stroke={isSelected ? '#ffffff' : conf.border}
                      strokeWidth={isSelected ? 3 : 2}
                      className="transition-all duration-300"
                    />
                    <text
                      x={pos.x}
                      y={pos.y + 4}
                      fill="#ffffff"
                      fontSize="10"
                      fontWeight="bold"
                      textAnchor="middle"
                    >
                      {node.label[0]}
                    </text>
                    <text
                      x={pos.x}
                      y={pos.y + 34}
                      fill={isDark ? "#ffffff" : "#000000"}
                      fontSize="10"
                      fontWeight="600"
                      textAnchor="middle"
                    >
                      {node.id.length > 12 ? `${node.id.slice(0, 10)}...` : node.id}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Right Node Inspector */}
        <div className="lg:col-span-4 bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
          <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            Entity Inspector
          </h3>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              <div className="p-3.5 rounded-xl bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 space-y-1">
                <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Selected Node</span>
                <div className="text-sm font-bold text-black dark:text-white">{selectedNode.title || selectedNode.id}</div>
                <div className="text-blue-600 dark:text-blue-400 font-mono text-xs">Type: {selectedNode.label}</div>
              </div>

              <div className="space-y-2">
                <span className="text-[10px] uppercase font-bold text-black/60 dark:text-white/60">Node Properties</span>
                {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between p-2 rounded-lg bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                    <span className="text-black/60 dark:text-white/60">{k}</span>
                    <span className="text-black dark:text-white font-mono font-bold">{String(v)}</span>
                  </div>
                ))}
              </div>

              <button
                onClick={() => {
                  setSearchType(selectedNode.label.toLowerCase() as any);
                  setSearchKey(selectedNode.id);
                  graphService.getSubgraph(selectedNode.label.toLowerCase(), selectedNode.id, 2).then((sub) => {
                    if (sub) setSubgraph(sub);
                  }).catch(() => {});
                }}
                className="w-full py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition cursor-pointer"
              >
                Expand From This Node →
              </button>
            </div>
          ) : (
            <div className="py-12 text-center text-black/60 dark:text-white/60 text-xs">
              Click any node in the canvas to inspect entity risk signals, connected transactions, and device sharing telemetry.
            </div>
          )}
        </div>
      </div>

      {/* Fraud Rings Syndicate Table */}
      <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4 transition-colors">
        <div>
          <h3 className="text-base font-bold text-black dark:text-white flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-red-600 dark:text-red-400" />
            Detected Fraud Rings & Collusion Clusters
          </h3>
          <p className="text-xs text-black/60 dark:text-white/60 mt-0.5">
            Syndicates identified via shared device fingerprints, IP proxy clusters, and cross-account coordination
          </p>
        </div>

        {loading && fraudRings.length === 0 ? (
          <LoadingSpinner text="Analyzing graph entity clusters..." />
        ) : fraudRings.length === 0 ? (
          <div className="text-center py-8 text-black/60 dark:text-white/60 text-sm">
            No active multi-user fraud rings detected in current window.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm text-black dark:text-white">
              <thead className="text-[11px] uppercase tracking-wider bg-black/5 dark:bg-white/5 text-black/60 dark:text-white/60 border-b border-black/10 dark:border-white/10">
                <tr>
                  <th className="px-4 py-3">Ring ID</th>
                  <th className="px-4 py-3">Entity Type</th>
                  <th className="px-4 py-3">Entity Key</th>
                  <th className="px-4 py-3">Linked Users</th>
                  <th className="px-4 py-3">Confirmed Fraud</th>
                  <th className="px-4 py-3">Total Fraud Amount</th>
                  <th className="px-4 py-3">Risk Tier</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/10 dark:divide-white/10">
                {fraudRings.map((r) => (
                  <tr key={r.ring_id} className="hover:bg-black/5 dark:hover:bg-white/5 transition">
                    <td className="px-4 py-3 font-mono font-bold text-blue-600 dark:text-blue-400">
                      {r.ring_id}
                    </td>
                    <td className="px-4 py-3 font-semibold text-black dark:text-white">
                      {r.entity_type}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-black/60 dark:text-white/60">
                      {r.entity_key}
                    </td>
                    <td className="px-4 py-3 font-bold text-black dark:text-white">
                      {r.user_count} accounts
                    </td>
                    <td className="px-4 py-3 font-bold text-red-600 dark:text-red-400">
                      {r.confirmed_fraud_count} txns
                    </td>
                    <td className="px-4 py-3 font-bold text-blue-600 dark:text-blue-400">
                      ${r.total_fraud_amount ? r.total_fraud_amount.toFixed(2) : '0.00'}
                    </td>
                    <td className="px-4 py-3">
                      <RiskBadge level={r.risk_level || 'High'} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleInspectRing(r)}
                        className="px-3 py-1 rounded-lg bg-blue-600/10 border border-blue-600/30 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20 text-xs font-semibold inline-flex items-center gap-1 cursor-pointer"
                      >
                        <span>Inspect Ring</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
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
