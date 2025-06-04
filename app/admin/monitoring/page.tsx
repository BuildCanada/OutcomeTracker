import React from 'react';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { Timestamp } from 'firebase-admin/firestore';
import UnifiedMonitoringDashboard from '../../../components/admin/UnifiedMonitoringDashboard';

export const metadata = {
  title: 'Pipeline Monitoring - Admin Dashboard',
  description: 'Monitor RSS feeds and Cloud Run pipeline job health and performance'
};

interface RSSMetrics {
  date: string;
  total_checks: number;
  successful_checks: number;
  total_bills_found: number;
  avg_response_time_ms: number;
  last_check: string | null;
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
  ingestion_type?: string;
  triggered_by?: string;
  check_type?: string;
  job_name?: string;
  stage?: string;
  source: 'rss' | 'pipeline';
}

// Helper function to serialize Firestore Timestamps
function serializeTimestamp(timestamp: Timestamp | undefined | null): string | null {
  if (!timestamp) return null;
  return timestamp.toDate().toISOString();
}

// Helper function to serialize data for client components
function serializeFirestoreData(data: any): any {
  if (!data) return data;
  
  const serialized = { ...data };
  
  // Convert Firestore Timestamps to ISO strings
  Object.keys(serialized).forEach(key => {
    if (serialized[key] && typeof serialized[key] === 'object' && '_seconds' in serialized[key]) {
      serialized[key] = serializeTimestamp(serialized[key]);
    }
    if (serialized[key] && serialized[key].toDate && typeof serialized[key].toDate === 'function') {
      serialized[key] = serialized[key].toDate().toISOString();
    }
  });
  
  return serialized;
}

async function getRSSMonitoringData() {
  try {
    // Get today's RSS metrics
    const today = new Date().toISOString().split('T')[0];
    const metricsDoc = await firestoreAdmin
      .collection('rss_feed_metrics')
      .doc(`daily_metrics_${today}`)
      .get();

    const todayMetricsRaw = metricsDoc.exists ? metricsDoc.data() : null;
    const todayMetrics = todayMetricsRaw ? serializeFirestoreData(todayMetricsRaw) : null;

    // Get last 7 days of RSS metrics for trending
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    
    const weeklyMetricsSnapshot = await firestoreAdmin
      .collection('rss_feed_metrics')
      .where('created_at', '>=', sevenDaysAgo)
      .orderBy('created_at', 'desc')
      .limit(7)
      .get();

    const weeklyMetrics = weeklyMetricsSnapshot.docs.map(doc => ({
      id: doc.id,
      ...serializeFirestoreData(doc.data())
    }));

    // Get RSS alerts
    const rssAlertsSnapshot = await firestoreAdmin
      .collection('rss_feed_alerts')
      .where('resolved', '==', false)
      .orderBy('created_at', 'desc')
      .limit(10)
      .get();

    const rssAlerts = rssAlertsSnapshot.docs.map(doc => ({
      id: doc.id,
      source: 'rss' as const,
      ...serializeFirestoreData(doc.data())
    }));

    // Get recent RSS activity (last 24 hours)
    const twentyFourHoursAgo = new Date();
    twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);

    const recentRSSActivitySnapshot = await firestoreAdmin
      .collection('rss_feed_monitoring')
      .where('start_time', '>=', twentyFourHoursAgo)
      .orderBy('start_time', 'desc')
      .limit(25)
      .get();

    const recentRSSActivity = recentRSSActivitySnapshot.docs.map(doc => ({
      id: doc.id,
      source: 'rss' as const,
      ...serializeFirestoreData(doc.data())
    }));

    return {
      todayMetrics,
      weeklyMetrics,
      rssAlerts,
      recentRSSActivity
    };

  } catch (error) {
    console.error('Error fetching RSS monitoring data:', error);
    return {
      todayMetrics: null,
      weeklyMetrics: [],
      rssAlerts: [],
      recentRSSActivity: []
    };
  }
}

async function getPipelineMonitoringData() {
  try {
    // Get recent pipeline job executions (last 24 hours)
    const twentyFourHoursAgo = new Date();
    twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);

    const pipelineExecutionsSnapshot = await firestoreAdmin
      .collection('pipeline_job_executions')
      .where('start_time', '>=', twentyFourHoursAgo)
      .orderBy('start_time', 'desc')
      .limit(50)
      .get();

    const pipelineExecutions = pipelineExecutionsSnapshot.docs.map(doc => ({
      id: doc.id,
      source: 'pipeline' as const,
      operation: 'pipeline_job' as const,
      ...serializeFirestoreData(doc.data())
    }));

    // Get pipeline alerts
    const pipelineAlertsSnapshot = await firestoreAdmin
      .collection('pipeline_alerts')
      .where('resolved', '==', false)
      .orderBy('created_at', 'desc')
      .limit(10)
      .get();

    const pipelineAlerts = pipelineAlertsSnapshot.docs.map(doc => ({
      id: doc.id,
      source: 'pipeline' as const,
      ...serializeFirestoreData(doc.data())
    }));

    // Calculate pipeline job stats by stage
    const jobStats: Record<string, { total: number; successful: number; failed: number; running: number }> = {
      ingestion: { total: 0, successful: 0, failed: 0, running: 0 },
      processing: { total: 0, successful: 0, failed: 0, running: 0 },
      linking: { total: 0, successful: 0, failed: 0, running: 0 },
      all: { total: 0, successful: 0, failed: 0, running: 0 }
    };

    pipelineExecutions.forEach(execution => {
      const stage = execution.stage || 'unknown';
      const status = execution.status || 'unknown';

      if (jobStats[stage]) {
        jobStats[stage].total += 1;
        if (status === 'success') jobStats[stage].successful += 1;
        else if (status === 'failed') jobStats[stage].failed += 1;
        else if (status === 'running') jobStats[stage].running += 1;
      }

      jobStats.all.total += 1;
      if (status === 'success') jobStats.all.successful += 1;
      else if (status === 'failed') jobStats.all.failed += 1;
      else if (status === 'running') jobStats.all.running += 1;
    });

    return {
      pipelineExecutions,
      pipelineAlerts,
      jobStats
    };

  } catch (error) {
    console.error('Error fetching pipeline monitoring data:', error);
    return {
      pipelineExecutions: [],
      pipelineAlerts: [],
      jobStats: {
        ingestion: { total: 0, successful: 0, failed: 0, running: 0 },
        processing: { total: 0, successful: 0, failed: 0, running: 0 },
        linking: { total: 0, successful: 0, failed: 0, running: 0 },
        all: { total: 0, successful: 0, failed: 0, running: 0 }
      }
    };
  }
}

async function getCloudRunServiceStatus() {
  try {
    // This would typically call the Cloud Run service health endpoint
    // For now, we'll return a mock status
    const serviceUrl = process.env.CLOUD_RUN_SERVICE_URL || 'https://promise-tracker-pipeline-2gbdayf7rq-uc.a.run.app';
    
    // In a real implementation, you'd make an HTTP request to the health endpoint
    // const response = await fetch(`${serviceUrl}/`);
    // const healthData = await response.json();
    
    return {
      serviceUrl,
      status: 'healthy', // This would come from the actual health check
      lastCheck: new Date().toISOString()
    };
  } catch (error) {
    console.error('Error checking Cloud Run service status:', error);
    return {
      serviceUrl: '',
      status: 'unknown',
      lastCheck: null
    };
  }
}

export default async function MonitoringPage({ 
  searchParams 
}: { 
  searchParams: { view?: string; feed?: string } 
}) {
  const selectedView = searchParams.view || 'overview';
  const selectedFeed = searchParams.feed || 'all';

  // Fetch all monitoring data in parallel
  const [rssData, pipelineData, cloudRunStatus] = await Promise.all([
    getRSSMonitoringData(),
    getPipelineMonitoringData(),
    getCloudRunServiceStatus()
  ]);

  // Combine alerts from both sources
  const allAlerts = [...rssData.rssAlerts, ...pipelineData.pipelineAlerts];

  // Combine recent activity from both sources
  const allRecentActivity = [...rssData.recentRSSActivity, ...pipelineData.pipelineExecutions]
    .sort((a, b) => {
      const aTime = new Date(a.start_time || 0).getTime();
      const bTime = new Date(b.start_time || 0).getTime();
      return bTime - aTime;
    })
    .slice(0, 50);

  // Calculate overall health status
  let overallHealthStatus = 'healthy';
  let overallSuccessRate = 100;

  // Check RSS health
  let rssSuccessRate = 100;
  if (rssData.todayMetrics && rssData.todayMetrics.total_checks > 0) {
    rssSuccessRate = (rssData.todayMetrics.successful_checks / rssData.todayMetrics.total_checks) * 100;
    if (rssSuccessRate < 80) overallHealthStatus = 'critical';
    else if (rssSuccessRate < 95) overallHealthStatus = 'warning';
  }

  // Check pipeline health
  const pipelineSuccessRate = pipelineData.jobStats.all.total > 0 
    ? (pipelineData.jobStats.all.successful / pipelineData.jobStats.all.total) * 100 
    : 100;
  
  if (pipelineSuccessRate < 80) overallHealthStatus = 'critical';
  else if (pipelineSuccessRate < 95 && overallHealthStatus === 'healthy') overallHealthStatus = 'warning';

  // Check for active alerts
  if (allAlerts.length > 0) {
    const hasCriticalAlerts = allAlerts.some(alert => alert.severity === 'critical');
    if (hasCriticalAlerts) overallHealthStatus = 'critical';
    else if (overallHealthStatus === 'healthy') overallHealthStatus = 'warning';
  }

  // Calculate combined success rate (already as percentage, don't multiply by 100 again)
  if (rssData.todayMetrics && rssData.todayMetrics.total_checks > 0) {
    overallSuccessRate = Math.round((rssSuccessRate + pipelineSuccessRate) / 2);
  } else {
    overallSuccessRate = Math.round(pipelineSuccessRate);
  }

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Pipeline Monitoring</h1>
        <p className="text-gray-600 mt-2">
          Monitor RSS feeds and Cloud Run pipeline jobs health and performance
        </p>
      </div>

      <UnifiedMonitoringDashboard 
        selectedView={selectedView}
        selectedFeed={selectedFeed}
        overallHealthStatus={overallHealthStatus}
        overallSuccessRate={overallSuccessRate}
        cloudRunStatus={cloudRunStatus}
        rssData={{
          todayMetrics: rssData.todayMetrics,
          weeklyMetrics: rssData.weeklyMetrics,
          recentActivity: rssData.recentRSSActivity
        }}
        pipelineData={{
          jobStats: pipelineData.jobStats,
          recentExecutions: pipelineData.pipelineExecutions
        }}
        allAlerts={allAlerts}
        allRecentActivity={allRecentActivity}
      />
    </div>
  );
} 