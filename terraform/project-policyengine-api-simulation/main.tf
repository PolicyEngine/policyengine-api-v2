locals {
    # Assumption from cost estimate. May need to tweak based on real performance.
    max_instance_request_concurrency = var.is_prod ? 80 : null
    # API is reachable if production otherwise internal-only.
    members = var.is_prod ? ["allUsers"] : ["allUsers"]
    # keep one instance running at all times in production for responsiveness.
    # in other environments don't waste the money
    service_scaling = var.is_prod ? {
        min_instance_count = 1
        max_instance_count = 10 # This seems like more than enough (800 concurrent requests)
    } : {
        max_instance_count = 1
    }

    # minimum instance specs only apply in production
    cpu_limit = var.is_prod ? "2" : null
    memory_limit = var.is_prod ? "1024Mi" : null

    container_image = "${var.region}-docker.pkg.dev/${ var.project_id }/api-v2/policyengine-api-simulation@${var.container_tag}"
}

# https://github.com/GoogleCloudPlatform/terraform-google-cloud-run/tree/main/modules/v2
module "cloud_run_v2" {
  source  = "GoogleCloudPlatform/cloud-run/google//modules/v2"
  version = "~> 0.16"

  service_name = "api-simulation"
  project_id   = var.project_id
  location     = "${var.region}"
  members     = local.members

  cloud_run_deletion_protection = false

  description = "PolicyEngine Simulation API"

  max_instance_request_concurrency =  local.max_instance_request_concurrency
  containers = [
    {
      container_image = local.container_image
      limits = {
        # as per the cost estimate we did for APIs.
        cpu    = local.cpu_limit
        memory = local.memory_limit
      }
    }
  ]
}

provider "google" {
  project = var.project_id
}

# Create a dedicated service account
resource "google_service_account" "default" {
  account_id   = "sample-workflows-sa"
  display_name = "Sample Workflows Service Account"
}

# Enable Workflows API
resource "google_project_service" "default" {
  service            = "workflows.googleapis.com"
  disable_on_destroy = false
}

# Create a workflow
resource "google_workflows_workflow" "default" {
  name            = "simulation-workflow"
  region          = "us-central1"
  description     = "Simulation workflow"
  service_account = google_service_account.default.id

  deletion_protection = false # set to "true" in production

  labels = {
    env = "test"
  }
  user_env_vars = {
    service_url = "${module.cloud_run_v2.service_uri}/simulate"
  }
  source_contents = file("../../projects/policyengine-api-simulation/workflow.yaml")

  depends_on = [google_project_service.default]
}