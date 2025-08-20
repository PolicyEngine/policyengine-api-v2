locals {
  api_image = "${var.region}-docker.pkg.dev/${ var.project_id }/api-v2/${ var.docker_repo }:${var.container_tag}"

  environment_variables = merge(
    { for k, v in var.environment_secrets : k => { secret = v } },
    { for k, v in var.env : k => { value = v } }
  )

  #force revision name to conform to limits...
  revision_name = substr(replace(
    lower("${var.name}-${substr(var.container_tag,0,7)}-${formatdate("YYYYMMDDhhmmss", timestamp())}"),
    "/[^a-z0-9-]/",  # Replace anything not lowercase, digit, or hyphen
    "-"
  ), 0, 63)
}

# Create a custom service account
resource "google_service_account" "api" {
  account_id   = "${var.name}"
  display_name = "Cloud Run Service Account for ${var.name} api"
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset(
    //basic roles required to write logs, metrics, traces + whatever the actual code requires
    concat(var.service_roles, ["roles/monitoring.metricWriter", "roles/logging.logWriter", "roles/cloudtrace.agent"]))
  project = var.project_id
  role = each.key
  member = "serviceAccount:${google_service_account.api.email}"
}

# https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service
resource "google_cloud_run_v2_service" "api" {
  provider = google-beta
  project = var.project_id
  name     = var.name
  location = var.region
  deletion_protection = false
  ingress = "INGRESS_TRAFFIC_ALL"

  description = var.description

  template {
    revision = local.revision_name
    service_account = google_service_account.api.email
    max_instance_request_concurrency = var.max_instance_request_concurrency
    containers {
      image = local.api_image
      resources {
        limits = {
          cpu    = var.limits.cpu
          memory = var.limits.memory
        }
        cpu_idle = var.request_based_billing ? true : false
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds = 1
        period_seconds = 5
        #Currently this high because simulation is so slow to load.
        failure_threshold = 24
        http_get {
          path = "/ping/started"
        }
      }

      liveness_probe {
        #once every 5 minutes
        period_seconds = 300 
        timeout_seconds = 1 
        failure_threshold = 2
        http_get {
          path = "/ping/alive"
        }
      }

      dynamic "env" {
        for_each = local.environment_variables
        content {
          name = env.key
    
          dynamic "value_source" {
            for_each = can(env.value.secret) ? [1] : []
            content {
              secret_key_ref {
                secret = env.value.secret
                version = "latest"
              }
            }
          }
    
          value = can(env.value.value) ? env.value.value : null
        }
      }
    }

    scaling {
      # always keep one instance hot in prod
      min_instance_count = var.min_instance_count
      # in beta don't create a bunch of containers
      # max in prod based on assumptions from cost estimate
      max_instance_count = var.max_instance_count
    }
    #Max timeout of 1 hour permitted.
    timeout = var.timeout
  }
}

data "google_project" "project" {
  project_id = var.project_id
}

data "google_iam_policy" "api" {
  binding {
    role = "roles/run.invoker"
    members = concat(var.members_can_invoke,
    [
      //support the monitor calling the api
      "serviceAccount:service-${data.google_project.project.number}@gcp-sa-monitoring-notification.iam.gserviceaccount.com"
    ])
  }
}

resource "google_cloud_run_service_iam_policy" "api" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name

  policy_data = data.google_iam_policy.api.policy_data
}
