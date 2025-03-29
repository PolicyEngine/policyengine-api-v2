

resource "google_monitoring_uptime_check_config" "cloudrun_health_check" {
  display_name = "${var.name} Health Check"
  # response time can be slower because of container spin up in beta.
  timeout      = var.is_prod ? "1s" : "10s"
  # don't waste resources waking up the beta container all the time. Just do it once a day.
  period       = var.is_prod ? "300s" : "900s"

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
  # in beta just check from the US to reduce cost
  # in prod check europe and the US since those are the two regions we currently primarily
  # operate in (pending multi-region expansion which we don't currently do)
  selected_regions = var.is_prod ? ["USA", "EUROPE_WEST"] : ["USA"]
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
  display_name = "${var.name} Health Check Alert"
  combiner     = "OR"
  
  conditions {
    display_name = "Uptime Check Failed"
    condition_prometheus_query_language {
        query = "avg by (check_id)(avg_over_time(monitoring_googleapis_com:uptime_check_check_passed{check_id=\"${google_monitoring_uptime_check_config.cloudrun_health_check.uptime_check_id}\", monitored_resource=\"uptime_url\"}[60s])) < 1"
        duration = "60s"
        evaluation_interval = "60s"
        alert_rule = "OnPresentAndFiring"
        rule_group = "health_checks"
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

  # Auto-close to reduce alert fatigue
  #alert_strategy {
  #  auto_close = var.is_prod ? "1800s" : "3600s" # 30 minutes for prod, 1 hour for non-prod
  #}
}

resource "google_monitoring_alert_policy" "limit_alert" {
  display_name = "${var.name} Limit Check"
  combiner     = "OR"
  
  conditions {
    display_name = "Memory usage over 75%"
    condition_prometheus_query_language {
        #go into the monitoring console, query metrics, select the thing you want to monitor and then select the prometheus view in order to get the right syntax for these.
        #the documentation is pretty bad and none of the LLMs, including google's, know how to do these properly.
        query = "histogram_quantile(0.95,sum by (le)(increase(run_googleapis_com:container_memory_utilizations_bucket{monitored_resource=\"cloud_run_revision\",service_name=\"${google_cloud_run_v2_service.api.name}\"}[1m]))) > .75"
        duration = "60s"
        evaluation_interval = "60s"
        alert_rule = "OnPresentAndFiring"
        rule_group = "health_checks"
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
  
