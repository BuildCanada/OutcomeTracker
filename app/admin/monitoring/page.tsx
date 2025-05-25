import React from 'react';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { Timestamp } from 'firebase-admin/firestore';
import RSSMonitoringDashboard from '../../../components/admin/RSSMonitoringDashboard';

export const metadata = {
  title: 'RSS Monitoring - Admin Dashboard',
  description: 'Monitor RSS feed health and ingestion performance'
};

interface RSSMetrics {
  date: string;
  total_checks: number;
  successful_checks: number;
  total_bills_found: number;
  avg_response_time_ms: number;
  last_check: Timestamp;
}

interface RSSAlert {
  id: string;
  alert_type: string;
  severity: 'warning' | 'critical';
  message: string;
  error_message?: string;
  failure_count: number;
  created_at: Timestamp;
  resolved: boolean;
}

interface RecentActivity {
  id: string;
  operation: 'rss_check' | 'bill_ingestion';
  status: string;
  start_time: Timestamp;
  end_time?: Timestamp;
  bills_found?: number;
  bills_processed?: number;
  evidence_created?: number;
  ingestion_type?: string;
  triggered_by?: string;
}

async function getMonitoringData() {
  try {
    // Get today's metrics
    const today = new Date().toISOString().split('T')[0];
    const metricsDoc = await firestoreAdmin
      .collection('rss_feed_metrics')
      .doc(`daily_metrics_${today}`)
      .get();

    const todayMetrics = metricsDoc.exists ? metricsDoc.data() as RSSMetrics : null;

    // Get last 7 days of metrics for trending
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
      ...doc.data()
    })) as (RSSMetrics & { id: string })[];

    // Get active alerts
    const alertsSnapshot = await firestoreAdmin
      .collection('rss_feed_alerts')
      .where('resolved', '==', false)
      .orderBy('created_at', 'desc')
      .limit(10)
      .get();

    const activeAlerts = alertsSnapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data()
    })) as RSSAlert[];

    // Get recent activity (last 24 hours)
    const twentyFourHoursAgo = new Date();
    twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);

    const recentActivitySnapshot = await firestoreAdmin
      .collection('rss_feed_monitoring')
      .where('start_time', '>=', twentyFourHoursAgo)
      .orderBy('start_time', 'desc')
      .limit(50)
      .get();

    const recentActivity = recentActivitySnapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data()
    })) as RecentActivity[];

    // Calculate health status
    let healthStatus = 'unknown';
    let successRate = 0;
    
    if (todayMetrics) {
      successRate = (todayMetrics.successful_checks / Math.max(todayMetrics.total_checks, 1)) * 100;
      
      if (successRate >= 95 && activeAlerts.length === 0) {
        healthStatus = 'healthy';
      } else if (successRate >= 80) {
        healthStatus = 'warning';
      } else {
        healthStatus = 'critical';
      }
    }

    return {
      healthStatus,
      successRate,
      todayMetrics,
      weeklyMetrics,
      activeAlerts,
      recentActivity
    };

  } catch (error) {
    console.error('Error fetching monitoring data:', error);
    return {
      healthStatus: 'error',
      successRate: 0,
      todayMetrics: null,
      weeklyMetrics: [],
      activeAlerts: [],
      recentActivity: []
    };
  }
}

export default async function MonitoringPage() {
  const monitoringData = await getMonitoringData();

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">RSS Feed Monitoring</h1>
        <p className="text-gray-600 mt-2">
          Monitor the health and performance of LEGISinfo RSS feed ingestion
        </p>
      </div>

      <RSSMonitoringDashboard 
        healthStatus={monitoringData.healthStatus}
        successRate={monitoringData.successRate}
        todayMetrics={monitoringData.todayMetrics}
        weeklyMetrics={monitoringData.weeklyMetrics}
        activeAlerts={monitoringData.activeAlerts}
        recentActivity={monitoringData.recentActivity}
      />
    </div>
  );
} 