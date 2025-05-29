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

interface PipelineJobExecution {
  id: string;
  job_name: string;
  stage: string;
  status: 'success' | 'failed' | 'running';
  start_time: string | null;
  end_time?: string | null;
  duration_seconds?: number;
  items_processed?: number;
  items_created?: number;
  items_updated?: number;
  items_skipped?: number;
  errors?: number;
  error_message?: string;
  triggered_by?: string;
  metadata?: any;
  source: 'pipeline';
  operation: 'pipeline_job';
}

interface Alert {
  id: string;
  alert_type: string;
  severity: 'warning' | 'critical';
  message: string;
  error_message?: string;
  failure_count: number;
  created_at: string | null;
  resolved: boolean;
  source: 'rss' | 'pipeline';
}

interface RecentActivity {
  id: string;
  operation: 'rss_check' | 'bill_ingestion' | 'pipeline_job';
  status: string;
  start_time: string | null;
  end_time?: string | null;
  bills_found?: number;
  bills_processed?: number;
  evidence_created?: number;
  items_created?: number;
  items_processed?: number;
  items_updated?: number;
  items_skipped?: number;
  errors?: number;
  error_message?: string;
  duration_seconds?: number;
  ingestion_type?: string;
  triggered_by?: string;
  check_type?: string;
  job_name?: string;
  stage?: string;
  source: 'rss' | 'pipeline';
}

interface CloudRunStatus {
  serviceUrl: string;
  status: string;
  lastCheck: string | null;
}

interface Props {
  selectedView: string;
  selectedFeed: string;
  overallHealthStatus: string;
  overallSuccessRate: number;
  cloudRunStatus: CloudRunStatus;
  rssData: {
    todayMetrics: RSSMetrics | null;
    weeklyMetrics: RSSMetrics[];
    recentActivity: RecentActivity[];
  };
  pipelineData: {
    jobStats: Record<string, { total: number; successful: number; failed: number; running: number }>;
    recentExecutions: PipelineJobExecution[];
  };
  allAlerts: Alert[];
  allRecentActivity: RecentActivity[];
}

const StatusBadge = ({ status }: { status: string }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-100 text-green-800 border-green-200';
      case 'warning': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'error': return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'success': return 'bg-green-100 text-green-800 border-green-200';
      case 'failed': return 'bg-red-100 text-red-800 border-red-200';
      case 'running': return 'bg-blue-100 text-blue-800 border-blue-200';
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

const formatDuration = (start: string | null, end?: string | null, durationSeconds?: number) => {
  if (durationSeconds) {
    if (durationSeconds < 60) return `${Math.round(durationSeconds)}s`;
    return `${Math.round(durationSeconds / 60)}m`;
  }
  
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

const getJobDisplayName = (jobName: string) => {
  const parts = jobName.split('.');
  if (parts.length === 2) {
    const [stage, job] = parts;
    return `${stage.charAt(0).toUpperCase() + stage.slice(1)}: ${job.replace(/_/g, ' ')}`;
  }
  return jobName.replace(/_/g, ' ');
};

export default function UnifiedMonitoringDashboard({
  selectedView,
  selectedFeed,
  overallHealthStatus,
  overallSuccessRate,
  cloudRunStatus,
  rssData,
  pipelineData,
  allAlerts,
  allRecentActivity
}: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleViewChange = (view: string) => {
    const params = new URLSearchParams(searchParams);
    if (view === 'overview') {
      params.delete('view');
    } else {
      params.set('view', view);
    }
    router.push(`/admin/monitoring?${params.toString()}`);
  };

  const handleFeedChange = (feedType: string) => {
    const params = new URLSearchParams(searchParams);
    if (feedType === 'all') {
      params.delete('feed');
    } else {
      params.set('feed', feedType);
    }
    router.push(`/admin/monitoring?${params.toString()}`);
  };

  const triggerPipelineJob = async (stage: string, jobName: string) => {
    try {
      const response = await fetch(`${cloudRunStatus.serviceUrl}/jobs/${stage}/${jobName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      });
      
      if (response.ok) {
        alert(`Job ${stage}.${jobName} triggered successfully!`);
        // Refresh the page to show updated data
        window.location.reload();
      } else {
        const error = await response.text();
        alert(`Failed to trigger job: ${error}`);
      }
    } catch (error) {
      alert(`Error triggering job: ${error}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* View Selector */}
      <div className="bg-white p-4 rounded-lg shadow border">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Pipeline Monitor</h3>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">View:</label>
              <select
                value={selectedView}
                onChange={(e) => handleViewChange(e.target.value)}
                className="block px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="overview">Overview</option>
                <option value="pipeline">Pipeline Jobs</option>
                <option value="rss">RSS Feeds</option>
                <option value="alerts">Alerts</option>
              </select>
            </div>
            
            {selectedView === 'rss' && (
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">Feed:</label>
                <select
                  value={selectedFeed}
                  onChange={(e) => handleFeedChange(e.target.value)}
                  className="block px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                >
                  <option value="all">All Feeds</option>
                  <option value="legisinfo_bills">LEGISinfo Bills</option>
                  <option value="canada_news_rss">Canada News RSS</option>
                </select>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Overview Dashboard */}
      {selectedView === 'overview' && (
        <>
          {/* Health Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-6 rounded-lg shadow border">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-500">Overall Health</h3>
                <StatusBadge status={overallHealthStatus} />
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {overallSuccessRate}%
              </p>
              <p className="text-xs text-gray-500 mt-1">Success rate today</p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow border">
              <h3 className="text-sm font-medium text-gray-500">Cloud Run Service</h3>
              <div className="flex items-center gap-2 mt-2">
                <StatusBadge status={cloudRunStatus.status} />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Last check: {formatTimestamp(cloudRunStatus.lastCheck)}
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow border">
              <h3 className="text-sm font-medium text-gray-500">Pipeline Jobs (24h)</h3>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {pipelineData.jobStats.all.total}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {pipelineData.jobStats.all.successful} successful, {pipelineData.jobStats.all.failed} failed
              </p>
            </div>

            <div className="bg-white p-6 rounded-lg shadow border">
              <h3 className="text-sm font-medium text-gray-500">Active Alerts</h3>
              <p className="text-2xl font-bold text-gray-900 mt-2">
                {allAlerts.length}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {allAlerts.filter(a => a.severity === 'critical').length} critical
              </p>
            </div>
          </div>

          {/* Pipeline Stage Stats */}
          <div className="bg-white p-6 rounded-lg shadow border">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Stages (24h)</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {['ingestion', 'processing', 'linking'].map(stage => {
                const stats = pipelineData.jobStats[stage];
                const successRate = stats.total > 0 ? (stats.successful / stats.total) * 100 : 0;
                
                return (
                  <div key={stage} className="p-4 border rounded-lg">
                    <h4 className="text-sm font-medium text-gray-900 capitalize">{stage}</h4>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-lg font-bold text-gray-900">{stats.total}</span>
                      <span className="text-sm text-gray-500">jobs</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-600">
                      {stats.successful} success, {stats.failed} failed, {stats.running} running
                    </div>
                    {stats.total > 0 && (
                      <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-green-500 h-2 rounded-full" 
                          style={{ width: `${successRate}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Pipeline Jobs View */}
      {selectedView === 'pipeline' && (
        <div className="bg-white rounded-lg shadow border">
          <div className="p-6 border-b">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Pipeline Jobs</h3>
              <a 
                href={cloudRunStatus.serviceUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                View Cloud Run Service →
              </a>
            </div>
          </div>
          
          {/* Job Controls */}
          <div className="p-6 border-b bg-gray-50">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Trigger Jobs</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {['ingestion', 'processing', 'linking'].map(stage => (
                <div key={stage} className="space-y-2">
                  <h5 className="text-xs font-medium text-gray-700 uppercase">{stage}</h5>
                  <div className="space-y-1">
                    {stage === 'ingestion' && (
                      <>
                        <button 
                          onClick={() => triggerPipelineJob('ingestion', 'canada_news')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Canada News
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('ingestion', 'legisinfo_bills')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          LEGISinfo Bills
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('ingestion', 'orders_in_council')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Orders in Council
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('ingestion', 'canada_gazette')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Canada Gazette
                        </button>
                      </>
                    )}
                    {stage === 'processing' && (
                      <>
                        <button 
                          onClick={() => triggerPipelineJob('processing', 'news_processor')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          News Processor
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('processing', 'bill_processor')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Bill Processor
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('processing', 'oic_processor')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          OIC Processor
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('processing', 'gazette_processor')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Gazette Processor
                        </button>
                      </>
                    )}
                    {stage === 'linking' && (
                      <>
                        <button 
                          onClick={() => triggerPipelineJob('linking', 'evidence_linker')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Evidence Linker
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('linking', 'progress_scorer')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Progress Scorer
                        </button>
                        <button 
                          onClick={() => triggerPipelineJob('linking', 'promise_enricher')}
                          className="w-full text-left px-3 py-2 text-sm bg-white border rounded hover:bg-gray-50"
                        >
                          Promise Enricher
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Pipeline Executions */}
          <div className="p-6">
            <h4 className="text-sm font-medium text-gray-900 mb-4">Recent Executions (24h)</h4>
            <div className="space-y-3">
              {pipelineData.recentExecutions.slice(0, 10).map(execution => (
                <div key={execution.id} className="flex items-center justify-between p-3 border rounded">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{getJobDisplayName(execution.job_name)}</span>
                      <StatusBadge status={execution.status} />
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Started: {formatTimestamp(execution.start_time)} • 
                      Duration: {formatDuration(execution.start_time, execution.end_time, execution.duration_seconds)}
                    </div>
                    {execution.items_created && execution.items_created > 0 && (
                      <div className="text-xs text-green-600 mt-1">
                        Created {execution.items_created} items
                      </div>
                    )}
                    {execution.error_message && (
                      <div className="text-xs text-red-600 mt-1">
                        Error: {execution.error_message}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {pipelineData.recentExecutions.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No pipeline executions in the last 24 hours
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* RSS Feeds View */}
      {selectedView === 'rss' && (
        <div className="bg-white rounded-lg shadow border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-medium text-gray-900">RSS Feed Monitoring</h3>
          </div>
          
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              <div className="p-4 border rounded-lg">
                <h4 className="text-sm font-medium text-gray-900">Today's Checks</h4>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {rssData.todayMetrics?.total_checks || 0}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {rssData.todayMetrics?.successful_checks || 0} successful
                </p>
              </div>
              
              <div className="p-4 border rounded-lg">
                <h4 className="text-sm font-medium text-gray-900">Bills Found</h4>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {rssData.todayMetrics?.total_bills_found || 0}
                </p>
                <p className="text-xs text-gray-500 mt-1">Today</p>
              </div>
              
              <div className="p-4 border rounded-lg">
                <h4 className="text-sm font-medium text-gray-900">Avg Response Time</h4>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {rssData.todayMetrics?.avg_response_time_ms || 0}ms
                </p>
                <p className="text-xs text-gray-500 mt-1">Today</p>
              </div>
            </div>

            <h4 className="text-sm font-medium text-gray-900 mb-4">Recent RSS Activity</h4>
            <div className="space-y-3">
              {rssData.recentActivity.slice(0, 10).map(activity => (
                <div key={activity.id} className="flex items-center justify-between p-3 border rounded">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{activity.check_type || activity.operation}</span>
                      <StatusBadge status={activity.status} />
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {formatTimestamp(activity.start_time)} • 
                      Duration: {formatDuration(activity.start_time, activity.end_time)}
                    </div>
                    {activity.bills_found && activity.bills_found > 0 && (
                      <div className="text-xs text-green-600 mt-1">
                        Found {activity.bills_found} bills
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {rssData.recentActivity.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No RSS activity in the last 24 hours
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Alerts View */}
      {selectedView === 'alerts' && (
        <div className="bg-white rounded-lg shadow border">
          <div className="p-6 border-b">
            <h3 className="text-lg font-medium text-gray-900">Active Alerts</h3>
          </div>
          
          <div className="p-6">
            <div className="space-y-4">
              {allAlerts.map(alert => (
                <div key={alert.id} className={`p-4 border rounded-lg ${
                  alert.severity === 'critical' ? 'border-red-200 bg-red-50' : 'border-yellow-200 bg-yellow-50'
                }`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={alert.severity} />
                        <span className="text-sm font-medium">{alert.alert_type}</span>
                        <span className="text-xs text-gray-500">({alert.source})</span>
                      </div>
                      <p className="text-sm text-gray-900 mt-2">{alert.message}</p>
                      {alert.error_message && (
                        <p className="text-xs text-gray-600 mt-1">Error: {alert.error_message}</p>
                      )}
                      <p className="text-xs text-gray-500 mt-2">
                        Created: {formatTimestamp(alert.created_at)} • 
                        Failure count: {alert.failure_count}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              
              {allAlerts.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No active alerts
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Recent Activity (shown on all views) */}
      <div className="bg-white rounded-lg shadow border">
        <div className="p-6 border-b">
          <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
        </div>
        
        <div className="p-6">
          <div className="space-y-3">
            {allRecentActivity.slice(0, 15).map(activity => (
              <div key={activity.id} className="flex items-center justify-between p-3 border rounded">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 bg-gray-100 rounded">{activity.source}</span>
                    <span className="font-medium text-sm">
                      {activity.source === 'pipeline' ? getJobDisplayName(activity.job_name || '') : (activity.check_type || activity.operation)}
                    </span>
                    <StatusBadge status={activity.status} />
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatTimestamp(activity.start_time)} • 
                    Duration: {formatDuration(activity.start_time, activity.end_time)}
                  </div>
                  {activity.items_created && activity.items_created > 0 && (
                    <div className="text-xs text-green-600 mt-1">
                      Created {activity.items_created} items
                    </div>
                  )}
                  {activity.bills_found && activity.bills_found > 0 && (
                    <div className="text-xs text-green-600 mt-1">
                      Found {activity.bills_found} bills
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {allRecentActivity.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                No recent activity
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 