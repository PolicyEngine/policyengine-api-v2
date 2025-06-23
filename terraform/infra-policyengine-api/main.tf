locals {
  use_hugging_face_token = var.hugging_face_token != ""
}

provider "google" {
  project = var.project_id
}

# Create a dedicated service account for workflow
resource "google_service_account" "workflow_sa" {
  account_id   = "simulation-workflows-sa"
  display_name = "Simulation Workflows Service Account"
}

module "cloud_run_full_api" {
  source = "./modules/fastapi_cloudrun"

  name = "full-api"
  description = "Full api containing all routes"
  docker_repo = "policyengine-api-full"
  container_tag = var.full_container_tag
  members_can_invoke = ["serviceAccount:tester@${var.project_id}.iam.gserviceaccount.com"]

  limits = {
    cpu    = var.is_prod ? 2 : null
    memory = var.is_prod ? "1024Mi" : null
  }

  project_id=var.project_id
  region=var.region
  slack_notification_channel_name=var.slack_notification_channel_name
  commit_url = var.commit_url

  uptime_timeout = "1s"
  min_instance_count = var.is_prod ? 1: 0
  max_instance_count = 2
  #guessing. Need to tune.
  max_instance_request_concurrency = var.is_prod ? 80: 1
  #this service should return basically immediately to all requests.
  timeout = "1s"

  enable_uptime_check = var.is_prod ? true : false
}

module "cloud_run_tagger_api" {
  source = "./modules/fastapi_cloudrun"

  name = "tagger-api"
  description = "API used to tag revisions for simulation api given a specific country package version"
  docker_repo = "policyengine-api-tagger"
  container_tag = var.tagger_container_tag
  members_can_invoke = ["serviceAccount:tester@${var.project_id}.iam.gserviceaccount.com"]

  env = {
    metadata_bucket_name =  google_storage_bucket.metadata.name
  }

  limits = {
    cpu    = var.is_prod ? 1 : null
    memory = var.is_prod ? "1024Mi" : null
  }

  project_id=var.project_id
  region=var.region
  slack_notification_channel_name=var.slack_notification_channel_name
  commit_url = var.commit_url

  uptime_timeout = "1s"
  min_instance_count = var.is_prod ? 1: 0
  max_instance_count = 1
  #guessing. Need to tune.
  max_instance_request_concurrency = var.is_prod ? 20: 1
  #this service should return basically immediately to all requests.
  timeout = "1s"

  enable_uptime_check = var.is_prod ? true : false
}

#give the tagger api access to the bucket
resource "google_storage_bucket_iam_member" "bucket_iam_tagger_member" {
  bucket = google_storage_bucket.metadata.name
  role   = "roles/storage.objectViewer"  # Example: Grant object viewer role
  member = "serviceAccount:${module.cloud_run_tagger_api.sa_email}"  # Example: Grant access to a user
}

#give permission to get and update cloudrun services (for tagging revisions)
#if you don't define your own permissions the closest role is run.developer which seems a bit expansive.
resource "google_project_iam_custom_role" "cloudrun_service_updater" {
  role_id     = "cloudRunServiceUpdater"
  title       = "Cloud Run Service Updater"
  description = "Can get and update Cloud Run services"
  permissions = [
    "run.services.get",
    "run.services.update"
  ]
}

resource "google_project_iam_member" "cloudrun_service_updater" {
  project = var.project_id
  role    = google_project_iam_custom_role.cloudrun_service_updater.name
  member  = "serviceAccount:${module.cloud_run_tagger_api.sa_email}"
}

# Grant permission to act as the simulation API service account
# This is required to update the service definition (which is required to modify the traffic definitions)
resource "google_service_account_iam_member" "cloudrun_act_as_simulation" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${module.cloud_run_simulation_api.sa_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${module.cloud_run_tagger_api.sa_email}"
}

module "cloud_run_simulation_api" {
  source = "./modules/fastapi_cloudrun"

  name = "api-simulation"
  description = "PolicyEngine Simulation API"
  container_tag = var.simulation_container_tag
  docker_repo = "policyengine-api-simulation"
  members_can_invoke = [
    "serviceAccount:tester@${var.project_id}.iam.gserviceaccount.com", 
    "serviceAccount:${google_service_account.workflow_sa.email}"]
  service_roles =  [
    "roles/secretmanager.secretAccessor"
  ]

  environment_secrets = local.use_hugging_face_token ? {
    "HUGGING_FACE_TOKEN" = google_secret_manager_secret.hugging_face_token[0].secret_id
  } : {}
  
  limits = {
    cpu = var.is_prod ? 8 : 4
    memory = var.is_prod ? "32Gi" : "16Gi"
  }

  project_id=var.project_id
  region=var.region
  slack_notification_channel_name=var.slack_notification_channel_name
  commit_url = var.commit_url

  uptime_timeout = var.is_prod ? "1s" : "30s"
  request_based_billing = true
  min_instance_count = var.is_prod ? 1: 0
  #arbitrary number. May need to tweak
  #permit at least 3 in beta so integration tests don't fail when run in parallel
  max_instance_count = var.is_prod ? 10 : 3
  #we are currently memory bound. internally it runs 2 handlers. keep one open for liveness checks.
  max_instance_request_concurrency = 1
  #permit max timeout since we run entire population simulations.
  timeout = "3600s"

  # This service can't really handle more than one request in a single container so
  # we don't use uptime check
  enable_uptime_check = false
}


# use google blobs to map versions of us and uk country packages.
# this allows us to coordinate with other services that require a specific version
# of these pacakges to be live before running.
resource "google_storage_bucket" "metadata" {
  name = "${var.project_id}-metadata"
  location      = "US"
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  force_destroy = true
}

locals {
  metadata = {
    uri      = module.cloud_run_simulation_api.uri
    revision = "projects/${var.project_id}/locations/${var.region}/services/${module.cloud_run_simulation_api.name}/revisions/${module.cloud_run_simulation_api.revision}"
    models = {
      us = var.policyengine-us-package-version
      uk = var.policyengine-uk-package-version
    }
  }
}

# Create the workflow for executing the simulation api
resource "google_workflows_workflow" "simulation_workflow" {
  name            = "simulation-workflow"
  region          = var.region
  description     = "Simulation workflow"
  service_account = google_service_account.workflow_sa.email

  deletion_protection = false # set to "true" in production

  labels = {
    env = var.is_prod ? "prod" : "test"
  }
  user_env_vars = {
    service_url = module.cloud_run_simulation_api.uri  # Just the hostname now
    service_path = "simulate/economy/comparison"        # Separate path
    tagger_service_url = "${module.cloud_run_tagger_api.uri}" 
  }
  source_contents = file("../../projects/policyengine-api-simulation/workflow.yaml")
}

# Grant the test service account permission to execute the workflow
resource "google_project_iam_member" "workflow_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:tester@${var.project_id}.iam.gserviceaccount.com"
}

# Grant the test service account permission to view workflow execution details
resource "google_project_iam_member" "workflow_viewer" {
  project = var.project_id
  role    = "roles/workflows.viewer"
  member  = "serviceAccount:tester@${var.project_id}.iam.gserviceaccount.com"
}

#Create a workflow for waiting for a specific set of country package versions to exist
resource "google_workflows_workflow" "wait_for_country_packages" {
  name            = "wait-for-country-packages"
  region          = var.region
  description     = "Workflow to wait for country packages to exist"
  service_account = google_service_account.workflow_sa.email

  deletion_protection = false 

  labels = {
    env = var.is_prod ? "prod" : "test"
  }
  source_contents = file("workflows/wait_for_country_versions.yaml")
}



# Grant necessary permissions to the workflow service account
resource "google_project_iam_member" "workflow_sa_permissions" {
  for_each = toset(["roles/workflows.invoker", "roles/run.invoker"])
  project = var.project_id
  role = each.key
  member = "serviceAccount:${google_service_account.workflow_sa.email}"
}


#give the workflow access to the bucket
resource "google_storage_bucket_iam_member" "bucket_iam_member" {
  bucket = google_storage_bucket.metadata.name
  role   = "roles/storage.objectViewer"  # Example: Grant object viewer role
  member = "serviceAccount:${google_service_account.workflow_sa.email}"  # Example: Grant access to a user
}

# Create a secret for the Hugging Face token
resource "google_secret_manager_secret" "hugging_face_token" {
  count = local.use_hugging_face_token == true ? 1 : 0
  secret_id = "hugging-face-token"
  
  replication {
    auto {}
  } 
}

# Add the secret version with the token value
resource "google_secret_manager_secret_version" "hugging_face_token" {
  count = local.use_hugging_face_token == true ? 1 : 0
  secret = google_secret_manager_secret.hugging_face_token[0].id
  secret_data = var.hugging_face_token
}
