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

  uptime_timeout = var.is_prod ? "1s" : "30s"
  min_instance_count = var.is_prod ? 1: 0
  max_instance_count = 2
  #guessing. Need to tune.
  max_instance_request_concurrency = var.is_prod ? 80: 1
  #this service should return basically immediately to all requests.
  timeout = "1s"

  enable_uptime_check = true
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
  max_instance_count = var.is_prod ? 10 : 1
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
}

locals {
  metadata = "{\"uri\":\"${module.cloud_run_simulation_api.uri}\",\"revision\":\"${module.cloud_run_simulation_api.latest_ready_revision}\",\"policyengine-us\":\"${var.policyengine-us-package-version}\",\"policyengine-uk\":\"${var.policyengine-uk-package-version}\"}"
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
    service_url = "${module.cloud_run_simulation_api.uri}/simulate/economy/comparison"
  }
  source_contents = file("../../projects/policyengine-api-simulation/workflow.yaml")
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
