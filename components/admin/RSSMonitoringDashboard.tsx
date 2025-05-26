'use client';

import React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

interface RSSMetrics {
  id?: string;
  date: string;
  total_checks: number;
  successful_checks: number;
  total_bills_found: number;
  avg_response_time_ms: number;
  last_check: string | null;
  created_at?: string | null;
}

interface RSSAlert {
  id: string;
  alert_type: string;
  severity: 'warning' | 'critical';
  message: string;
  error_message?: string;
  failure_count: number;
  created_at: string | null;
  resolved: boolean;
}

interface RecentActivity {
  id: string;
  operation: 'rss_check' | 'bill_ingestion';
  status: string;
  start_time: string | null;
  end_time?: string | null;
  bills_found?: number;
  bills_processed?: number;
  evidence_created?: number;
  ingestion_type?: string;
  triggered_by?: string;
  check_type?: string;
}

interface Props {
  healthStatus: string;
  successRate: number;
  todayMetrics: RSSMetrics | null;
  weeklyMetrics: RSSMetrics[];
  activeAlerts: RSSAlert[];
  recentActivity: RecentActivity[];
  feedStats: Record<string, { total: number; successful: number; bills_found: number }>;
  selectedFeed: string;
}

const StatusBadge = ({ status }: { status: string }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-100 text-green-800 border-green-200';
      case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'error': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(status)}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

const formatTimestamp = (timestamp: string | null) => {
  if (!timestamp) return 'Never';
  
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return 'Invalid date';
  }
};

const formatDuration = (start: string | null, end?: string | null) => {
  if (!start) return 'Unknown';
  if (!end) return 'In progress...';
  
  try {
    const startMs = new Date(start).getTime();
    const endMs = new Date(end).getTime();
    const durationMs = endMs - startMs;
    
    if (durationMs < 1000) return `${durationMs}ms`;
    if (durationMs < 60000) return `${Math.round(durationMs / 1000)}s`;
    return `${Math.round(durationMs / 60000)}m`;
  } catch {
    return 'Unknown';
  }
};

export default function RSSMonitoringDashboard({
  healthStatus,
  successRate,
  todayMetrics,
  weeklyMetrics,
  activeAlerts,
  recentActivity,
  feedStats,
  selectedFeed
}: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleFeedChange = (feedType: string) => {
    const params = new URLSearchParams(searchParams);
    if (feedType === 'all') {
      params.delete('feed');
    } else {
      params.set('feed', feedType);
    }
    router.push(`/admin/monitoring?${params.toString()}`);
  };

  const getFeedDisplayName = (feedType: string) => {
    switch (feedType) {
      case 'legisinfo_bills': return 'LEGISinfo Bills';
      case 'canada_news_rss': return 'Canada News RSS';
      case 'all': return 'All Feeds';
      default: return feedType;
    }
  };

  const currentFeedStats = feedStats[selectedFeed] || feedStats.all;

  return (
    <div className="space-y-6">
      {/* Feed Selector */}
      <div className="bg-white p-4 rounded-lg shadow border">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">RSS Feed Monitor</h3>
          <div className="flex items-center gap-4">
            <label htmlFor="feed-select" className="text-sm font-medium text-gray-700">
              View Feed:
            </label>
            <select
              id="feed-select"
              value={selectedFeed}
              onChange={(e) => handleFeedChange(e.target.value)}
              className="block w-48 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            >
              <option value="all">All Feeds</option>
              <option value="legisinfo_bills">LEGISinfo Bills</option>
              <option value="canada_news_rss">Canada News RSS</option>
            </select>
          </div>
        </div>
        
        {/* Feed Stats Summary */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(feedStats).map(([feedType, stats]) => (
            <div key={feedType} className={`p-3 rounded border ${
              selectedFeed === feedType ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200'
            }`}>
              <h4 className="text-sm font-medium text-gray-900">{getFeedDisplayName(feedType)}</h4>
              <div className="mt-1 text-xs text-gray-600">
                {stats.total} checks, {stats.successful} successful, {stats.bills_found} bills found
              </div>
              {stats.total > 0 && (
                <div className="mt-1 w-full bg-gray-200 rounded-full h-1.5">
                  <div 
                    className="bg-green-500 h-1.5 rounded-full" 
                    style={{ width: `${(stats.successful / stats.total) * 100}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow border">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-500">Feed Health</h3>
            <StatusBadge status={healthStatus} />
          </div>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {Math.round(successRate)}%
          </p>
          <p className="text-xs text-gray-500 mt-1">Success rate today</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-sm font-medium text-gray-500">Checks Today</h3>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {todayMetrics?.total_checks || 0}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {todayMetrics?.successful_checks || 0} successful
          </p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-sm font-medium text-gray-500">Evidence Found Today</h3>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {todayMetrics?.total_bills_found || 0}
          </p>
          <p className="text-xs text-gray-500 mt-1">Total discovered</p>
        </div>

        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-sm font-medium text-gray-500">Avg Response Time</h3>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {Math.round(todayMetrics?.avg_response_time_ms || 0)}ms
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Last check: {formatTimestamp(todayMetrics?.last_check || null)}
          </p>
        </div>
      </div>

      {/* Active Alerts */}
      {activeAlerts.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Active Alerts</h3>
          <div className="space-y-3">
            {activeAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 rounded-lg border ${
                  alert.severity === 'critical' 
                    ? 'bg-red-50 border-red-200' 
                    : 'bg-yellow-50 border-yellow-200'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={alert.severity} />
                      <span className="text-sm font-medium text-gray-900">
                        {alert.alert_type.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{alert.message}</p>
                    {alert.error_message && (
                      <p className="text-xs text-gray-500 mt-1 font-mono">
                        {alert.error_message}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatTimestamp(alert.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weekly Trend */}
      <div className="bg-white p-6 rounded-lg shadow border">
        <h3 className="text-lg font-medium text-gray-900 mb-4">7-Day Trend</h3>
        {weeklyMetrics.length > 0 ? (
          <div className="space-y-2">
            {weeklyMetrics.map((metric) => {
              const dailySuccessRate = (metric.successful_checks / Math.max(metric.total_checks, 1)) * 100;
              return (
                <div key={metric.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                  <span className="text-sm text-gray-900">{metric.date}</span>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-600">{metric.total_checks} checks</span>
                    <span className="text-gray-600">{metric.total_bills_found} bills</span>
                    <div className="flex items-center gap-1">
                      <div className="w-12 bg-gray-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full ${
                            dailySuccessRate >= 95 ? 'bg-green-500' : 
                            dailySuccessRate >= 80 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${dailySuccessRate}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">{Math.round(dailySuccessRate)}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">No historical data available</p>
        )}
      </div>

      {/* Recent Activity */}
      <div className="bg-white p-6 rounded-lg shadow border">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity (24h)</h3>
        {recentActivity.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Operation
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Results
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Time
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {recentActivity.slice(0, 20).map((activity) => (
                  <tr key={activity.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {activity.operation === 'rss_check' ? 'RSS Check' : 'Bill Ingestion'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {activity.check_type && getFeedDisplayName(activity.check_type)}
                        {activity.ingestion_type && (
                          <span> - {activity.ingestion_type} ({activity.triggered_by})</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={activity.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {activity.operation === 'rss_check' ? (
                        `${activity.bills_found || 0} items found`
                      ) : (
                        `${activity.bills_processed || 0} processed, ${activity.evidence_created || 0} evidence`
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDuration(activity.start_time, activity.end_time)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatTimestamp(activity.start_time)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">No recent activity</p>
        )}
      </div>
    </div>
  );
} 