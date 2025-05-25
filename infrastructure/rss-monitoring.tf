# RSS Feed Monitoring Infrastructure
# This file sets up the Google Cloud resources for RSS feed monitoring

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

# Cloud Scheduler Job for RSS checks
resource "google_cloud_scheduler_job" "rss_check" {
  name             = "rss-feed-check"
  description      = "Check RSS feed every 30 minutes for bill updates"
  schedule         = "*/30 * * * *"  # Every 30 minutes
  time_zone        = "America/Toronto"
  attempt_deadline = "320s"

  retry_config {
    retry_count = 3
  }

  http_target {
    http_method = "POST"
    uri         = google_cloud_run_service.rss_monitor.status[0].url

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      action = "rss_check"
      hours_threshold = 1
      parliament_filter = 44
    }))

    oidc_token {
      service_account_email = google_service_account.rss_monitor.email
    }
  }
}

# Cloud Scheduler Job for daily full ingestion (fallback)
resource "google_cloud_scheduler_job" "daily_ingestion" {
  name             = "daily-bill-ingestion"
  description      = "Daily RSS-driven bill ingestion"
  schedule         = "0 6 * * *"  # 6 AM daily
  time_zone        = "America/Toronto"
  attempt_deadline = "1800s"  # 30 minutes

  retry_config {
    retry_count = 2
  }

  http_target {
    http_method = "POST"
    uri         = google_cloud_run_service.rss_monitor.status[0].url

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode(jsonencode({
      action = "full_ingestion"
      hours_threshold = 24
      parliament_filter = 44
      fallback_full_run = true
    }))

    oidc_token {
      service_account_email = google_service_account.rss_monitor.email
    }
  }
}

# Service Account for RSS monitoring
resource "google_service_account" "rss_monitor" {
  account_id   = "rss-monitor"
  display_name = "RSS Feed Monitor Service Account"
  description  = "Service account for RSS feed monitoring and bill ingestion"
}

# Grant Firestore permissions
resource "google_project_iam_member" "rss_monitor_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.rss_monitor.email}"
}

# Grant Cloud Run permissions
resource "google_project_iam_member" "rss_monitor_run" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.rss_monitor.email}"
}

# Cloud Run service for RSS monitoring
resource "google_cloud_run_service" "rss_monitor" {
  name     = "rss-monitor"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/rss-monitor"
        
        env {
          name  = "FIREBASE_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }

      service_account_name = google_service_account.rss_monitor.email
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"      = "10"
        "run.googleapis.com/execution-environment" = "gen2"
        "run.googleapis.com/cpu-throttling"     = "false"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_iam_member.rss_monitor_firestore]
}

# Allow unauthenticated access (protected by IAM)
resource "google_cloud_run_service_iam_member" "rss_monitor_invoker" {
  service  = google_cloud_run_service.rss_monitor.name
  location = google_cloud_run_service.rss_monitor.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.rss_monitor.email}"
}

# Cloud Monitoring Alert Policy for RSS failures
resource "google_monitoring_alert_policy" "rss_failure_alert" {
  display_name = "RSS Feed Failure Alert"
  combiner     = "OR"
  
  conditions {
    display_name = "RSS Check Failure Rate"
    
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GREATER_THAN"
      threshold_value = 0.1  # 10% failure rate
      duration        = "300s"  # 5 minutes
      
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields = ["resource.service_name"]
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.email.name
  ]

  alert_strategy {
    auto_close = "86400s"  # 24 hours
  }
}

# Email notification channel
resource "google_monitoring_notification_channel" "email" {
  display_name = "RSS Monitoring Email"
  type         = "email"
  
  labels = {
    email_address = "admin@your-domain.com"  # Update this
  }
}

# Cloud Storage bucket for exports and backups
resource "google_storage_bucket" "rss_monitoring_data" {
  name          = "${var.project_id}-rss-monitoring-data"
  location      = var.region
  storage_class = "REGIONAL"

  lifecycle_rule {
    condition {
      age = 90  # Keep data for 90 days
    }
    action {
      type = "Delete"
    }
  }

  versioning {
    enabled = true
  }
}

# Outputs
output "rss_monitor_service_url" {
  description = "URL of the RSS monitor Cloud Run service"
  value       = google_cloud_run_service.rss_monitor.status[0].url
}

output "rss_monitor_service_account" {
  description = "Email of the RSS monitor service account"
  value       = google_service_account.rss_monitor.email
} 