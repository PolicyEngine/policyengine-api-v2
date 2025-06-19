

resource "google_monitoring_uptime_check_config" "cloudrun_health_check" {
  for_each = var.enable_uptime_check ? toset(["0"]) : toset([])
  display_name = "${var.name} Health Check"
  # response time can be slower because of container spin up in beta.
  timeout      = var.uptime_timeout
  # once every 5 minutes
  period       = "300s"

  http_check {
    path         = "/ping/alive"
    port         = "443"
    use_ssl      = true
    validate_ssl = true
    service_agent_authentication {
      type = "OIDC_TOKEN"
      
    }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       =  regex("://([^/:]+)", google_cloud_run_v2_service.api.uri)[0]
    }
  }

  # See https://github.com/PolicyEngine/policyengine-api-v2/issues/117
  # we are not yet multi-regional so just check the places we operate in.
  # https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.uptimeCheckConfigs#UptimeCheckRegion
  selected_regions = ["USA", "EUROPE"]
}

# Only reference the Slack notification channel if the variable is not empty
locals {
  use_slack_notification = var.slack_notification_channel_name != ""
  notification_channels = local.use_slack_notification ? [data.google_monitoring_notification_channel.slack[0].name] : []
}

#You need to do this in the console
# Reference an existing Slack notification channel that was set up in the console
data "google_monitoring_notification_channel" "slack" {
  count        = local.use_slack_notification ? 1 : 0
  display_name = var.slack_notification_channel_name
}

# Create the alerting policy with PromQL that references your uptime check
resource "google_monitoring_alert_policy" "cloudrun_health_alert" {
  for_each = var.enable_uptime_check ? toset(["0"]) : ([])
  display_name = "${var.name} Health Check Alert"
  combiner     = "OR"
  
  conditions {
    display_name = "Uptime Check Failed"
    condition_prometheus_query_language {
        query = "avg by (check_id)(avg_over_time(monitoring_googleapis_com:uptime_check_check_passed{check_id=\"${google_monitoring_uptime_check_config.cloudrun_health_check[0].uptime_check_id}\", monitored_resource=\"uptime_url\"}[60s])) < 1"
        #fail two consecutive checks (5 minutes)
        duration = "600s" #10m
        labels = {
          severity = "critical"
        }
    }
  }

  notification_channels = local.notification_channels

  # Add documentation with more detailed information for Slack messages
  documentation {
  content = <<-EOT
      🚨 *${var.name} Service Health Alert*

      The ${var.name} service is failing its health check at endpoint `/ping/alive`.

      *Troubleshooting Steps:*
      - Check the [${var.name} Cloud Run service](https://console.cloud.google.com/run/detail/${var.region}/${var.name}/metrics?project=${var.project_id})
      - Check the [latest changes](${var.commit_url})
      EOT
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "limit_alert" {
  display_name = "${var.name} Limit Check"
  combiner     = "OR"
  
  conditions {
    display_name = "Memory usage over 90%"
    condition_prometheus_query_language {
        #go into the monitoring console, query metrics, select the thing you want to monitor and then select the prometheus view in order to get the right syntax for these.
        #the documentation is pretty bad and none of the LLMs, including google's, know how to do these properly.
        query = "histogram_quantile(0.95,sum by (le)(increase(run_googleapis_com:container_memory_utilizations_bucket{monitored_resource=\"cloud_run_revision\",service_name=\"${google_cloud_run_v2_service.api.name}\"}[1m]))) > .9"
        #if the memory jumps above 90% immediately notify the team in slack that we're approaching our limit.
        duration = "60s"
        evaluation_interval = "60s"
        labels = {
          severity = "critical"
        }
    }
  }

  notification_channels = local.notification_channels

  # Add documentation with more detailed information for Slack messages
  documentation {
  content = <<-EOT
      🚨 *${var.name} Service Limit Alert*

      The ${var.name}'s has exceeded resource limits. Check the related policy to see which one.

      *Troubleshooting Steps:*
      - Check the [${var.name} Cloud Run service](https://console.cloud.google.com/run/detail/${var.region}/${var.name}/metrics?project=${var.project_id})
      - Check the [latest changes](${var.commit_url})
      EOT
    mime_type = "text/markdown"
  }
}
  
resource "google_monitoring_alert_policy" "simulation_workflow_failure" {
  display_name = "Simulation Workflow Failures (for tf test)"
  combiner     = "OR"

  conditions {
    display_name = "Simulation Workflow Failed in Last 5 Minutes"

    condition_threshold {
      filter = <<-EOT
        metric.type="workflows.googleapis.com/workflow/execution_count"
        AND resource.type="cloud_workflow"
        AND metric.label."status"="FAILED"
        AND resource.label."workflow_name"="policyengine-api-simulation"
      EOT

      duration        = "300s"  # 5-minute window
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = local.notification_channels

  documentation {
    content   = <<-EOT
      🚨 *Simulation Workflow Failure Alert*

      One or more executions of the simulation workflow failed within the last 5 minutes.

      *Steps:*
      - Check Cloud Workflows logs
      - Confirm input data
      - Review recent deploys: [Latest commit](${var.commit_url})
    EOT
    mime_type = "text/markdown"
  }

  user_labels = {
    service = "policyengine-api"
    type    = "workflow-alert"
  }

  enabled = true
}

