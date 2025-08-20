locals {
  base_project_id = "${var.stage}-${var.project_name}"
}

provider "google" {
  region = var.region
}

provider "google-beta" {
  region = var.region
}

module "project" {
  source  = "terraform-google-modules/project-factory/google"
  version = "~> 18.0"

  name                 = local.base_project_id
  random_project_id    = true
  org_id               = var.org_id
  bucket_force_destroy = var.is_prod ? false : true
  billing_account      = var.billing_account
  project_sa_name      = "project" # email will include the project name which in turn has stage
  bucket_project       = local.base_project_id

  default_service_account = "deprivilege"
  deletion_policy = var.is_prod ? "PREVENT" : "DELETE"
  

  # revisit cloud armor, budget alarm, etc.
  

  activate_apis = [
    # requirements to build and deploy a cloudrun container
    # https://cloud.google.com/build/docs/build-push-docker-image
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com", 
    "run.googleapis.com",
    # required to deploy terraform
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    # to orchestrate our simulation runs
    "workflows.googleapis.com",
    # to support tracelogs and metrics from our services
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com",
    # to store microdata token for pulling data
    "secretmanager.googleapis.com"]
}

#Availability monitors optionally auth with ODIC, but you cannot configure
#which service account they use, they HAVE to use the default service account
#As of writing it won't complain when you tell it to auth and the default monitoring
#SA doesn't exist, it will just not authenticate :/
#Anyway, this is forcing creation according to https://cloud.google.com/iam/docs/create-service-agents#create-service-agent-terraform
resource "google_project_service_identity" "mon_sa" {
  provider = google-beta

  project =  module.project.project_id
  service = "monitoring.googleapis.com"
}

resource "google_storage_bucket" "logs" {
  project = module.project.project_id
  name = "${module.project.project_id}-buildlogs"
  location = "US"
  uniform_bucket_level_access = true
  force_destroy = true
}

resource "google_storage_bucket_iam_binding" "binding" {
  bucket = google_storage_bucket.logs.name
  role = "roles/storage.admin"
  members = [
    "serviceAccount:${data.google_service_account.default_compute.email}",
  ]
}

resource "google_service_account" "deploy" {
  project = module.project.project_id
  account_id = "deploy"
  description = "Service account for deploying to/updating this project"
}

resource "google_project_iam_member" "deploy_service_account_roles" {
  for_each = toset(["roles/owner"])
  project = module.project.project_id
  role = each.key
  member = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account" "tester" {
  project = module.project.project_id
  account_id = "tester"
  description = "Service account for running integration tests"
}

# Workflow service account moved to infra-policyengine-api/main.tf

#Look up the default compute account so we can add back in permissions.
data "google_service_account" "default_compute" {
  account_id = "${module.project.project_number}-compute@developer.gserviceaccount.com"
  depends_on = [ module.project]
}


#Give the detault compute account the roles required to build and store artifacts.
resource "google_project_iam_member" "compute-service-account-roles" {
  for_each = toset(["roles/artifactregistry.writer", "roles/storage.objectUser"])
  project = module.project.project_id
  role = each.key
  member = "serviceAccount:${data.google_service_account.default_compute.email}"
}


//service account for building stuff
resource "google_service_account" "build" {
  project = module.project.project_id
  account_id = "builder" #email will contain the  project id which has stage.
  description = "service account for starting artifact builds."
}

//Needs to be able to submit builds.
resource "google_project_iam_member" "build-service-account-roles" {
  for_each = toset(["roles/cloudbuild.builds.builder"])
  project = module.project.project_id
  role = each.key
  member = "serviceAccount:${google_service_account.build.email}"
}

//and also in turn, needs to be able to use the compute service account.
resource "google_service_account_iam_binding" "compute-service-iam" {
  service_account_id = data.google_service_account.default_compute.id
  role               = "roles/iam.serviceAccountUser"
  members = [
    "serviceAccount:${google_service_account.build.email}"
  ]
}

# Repository for storing docker artifacts, etc.
resource "google_artifact_registry_repository" "docker_repo" {
    repository_id = "api-v2"
    description = "Docker repo for images created under the ${module.project.project_name} project"
    format = "DOCKER"
    project = module.project.project_id
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.stage}-github-${var.project_name}"
  display_name              = substr("${var.stage} github identity pool",0,32)
  description               = "Identity pool for github actions"
  project = module.project.project_id
  disabled                  = false
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "${var.stage}-github-${var.project_name}"
  display_name                       = "${var.stage} Github provider"
  description                        = "GitHub Actions identity pool provider"
  project = module.project.project_id
  disabled                           = false
  attribute_condition = <<EOT
    assertion.repository_owner_id == "${var.github_repo_owner_id}" &&
    attribute.repository == "${var.github_repo}" &&
    assertion.ref == "${var.github_repo_ref}" &&
    assertion.ref_type == "branch"
EOT
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
    "attribute.repository" = "assertion.repository"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}


# And let it access the build service principal
#Look up the default compute account so we can add back in permissions.
resource "google_service_account_iam_member" "github_impersonate_permissions" {
  for_each = { 
    build = google_service_account.build.name, 
    deploy = google_service_account.deploy.name,
    test = google_service_account.tester.name}
  service_account_id = each.value
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

locals {
  //for some reason they don't export the bucket, just the url. And that as an array.
  //pull the one and only one bucket url and get the bucket name
  project_bucket = trimprefix(module.project.project_bucket_url[0], "gs://")
}

//this will bottstrap our backend.tf to use the state bucket after we've 
//created the project.
//https://cloud.google.com/docs/terraform/resource-management/store-state
resource "local_file" "default" {
  file_permission = "0644"
  filename        = "${path.cwd}/backend.tf"
  content = <<-EOT
  terraform {
    backend "gcs" {
      bucket = "${local.project_bucket}"
      prefix = "terraform/project"
    }
  }
  EOT
}
