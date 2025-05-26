import React from 'react';
import { firestoreAdmin } from '@/lib/firebaseAdmin';
import { Timestamp } from 'firebase-admin/firestore';
import RSSMonitoringDashboard from '../../../components/admin/RSSMonitoringDashboard';

export const metadata = {
  title: 'RSS Monitoring - Admin Dashboard',
  description: 'Monitor RSS feed health and ingestion performance across multiple sources'
};

interface RSSMetrics {
  date: string;
  total_checks: number;
  successful_checks: number;
  total_bills_found: number;
  avg_response_time_ms: number;
  last_check: string | null;
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

async function getMonitoringData(feedType?: string) {
  try {
    // Get today's metrics
    const today = new Date().toISOString().split('T')[0];
    const metricsDoc = await firestoreAdmin
      .collection('rss_feed_metrics')
      .doc(`daily_metrics_${today}`)
      .get();

    const todayMetricsRaw = metricsDoc.exists ? metricsDoc.data() : null;
    const todayMetrics = todayMetricsRaw ? serializeFirestoreData(todayMetricsRaw) : null;

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
      ...serializeFirestoreData(doc.data())
    }));

    // Get active alerts
    const alertsSnapshot = await firestoreAdmin
      .collection('rss_feed_alerts')
      .where('resolved', '==', false)
      .orderBy('created_at', 'desc')
      .limit(10)
      .get();

    const activeAlerts = alertsSnapshot.docs.map(doc => ({
      id: doc.id,
      ...serializeFirestoreData(doc.data())
    }));

    // Get recent activity (last 24 hours)
    const twentyFourHoursAgo = new Date();
    twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);

    let recentActivityQuery = firestoreAdmin
      .collection('rss_feed_monitoring')
      .where('start_time', '>=', twentyFourHoursAgo);

    // Filter by feed type if specified
    if (feedType && feedType !== 'all') {
      recentActivityQuery = recentActivityQuery.where('check_type', '==', feedType);
    }

    const recentActivitySnapshot = await recentActivityQuery
      .orderBy('start_time', 'desc')
      .limit(50)
      .get();

    const recentActivity = recentActivitySnapshot.docs.map(doc => ({
      id: doc.id,
      ...serializeFirestoreData(doc.data())
    }));

    // Get feed summary stats for all feeds
    const allActivitySnapshot = await firestoreAdmin
      .collection('rss_feed_monitoring')
      .where('start_time', '>=', twentyFourHoursAgo)
      .get();

    const feedStats: Record<string, { total: number; successful: number; bills_found: number }> = {
      legisinfo_bills: { total: 0, successful: 0, bills_found: 0 },
      canada_news_rss: { total: 0, successful: 0, bills_found: 0 },
      all: { total: 0, successful: 0, bills_found: 0 }
    };

    allActivitySnapshot.docs.forEach(doc => {
      const data = doc.data();
      const checkType = data.check_type || 'unknown';
      const success = data.success === true;
      const billsFound = data.bills_found || 0;

      if (feedStats[checkType]) {
        feedStats[checkType].total += 1;
        if (success) feedStats[checkType].successful += 1;
        feedStats[checkType].bills_found += billsFound;
      }

      feedStats.all.total += 1;
      if (success) feedStats.all.successful += 1;
      feedStats.all.bills_found += billsFound;
    });

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
      recentActivity,
      feedStats
    };

  } catch (error) {
    console.error('Error fetching monitoring data:', error);
    return {
      healthStatus: 'error',
      successRate: 0,
      todayMetrics: null,
      weeklyMetrics: [],
      activeAlerts: [],
      recentActivity: [],
      feedStats: {
        legisinfo_bills: { total: 0, successful: 0, bills_found: 0 },
        canada_news_rss: { total: 0, successful: 0, bills_found: 0 },
        all: { total: 0, successful: 0, bills_found: 0 }
      }
    };
  }
}

export default async function MonitoringPage({ 
  searchParams 
}: { 
  searchParams: { feed?: string } 
}) {
  const selectedFeed = searchParams.feed || 'all';
  const monitoringData = await getMonitoringData(selectedFeed);

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">RSS Feed Monitoring</h1>
        <p className="text-gray-600 mt-2">
          Monitor the health and performance of RSS feed ingestion from multiple sources
        </p>
      </div>

      <RSSMonitoringDashboard 
        healthStatus={monitoringData.healthStatus}
        successRate={monitoringData.successRate}
        todayMetrics={monitoringData.todayMetrics}
        weeklyMetrics={monitoringData.weeklyMetrics}
        activeAlerts={monitoringData.activeAlerts}
        recentActivity={monitoringData.recentActivity}
        feedStats={monitoringData.feedStats}
        selectedFeed={selectedFeed}
      />
    </div>
  );
} 