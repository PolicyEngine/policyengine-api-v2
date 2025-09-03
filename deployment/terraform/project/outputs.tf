output "project_bucket" {
    value = local.project_bucket
    description = "bucket for storing project terraform state"
}

output "stage" {
    value = var.stage
    description = "stage configured for this project"
}

output "project_id" {
    value = module.project.project_id
    description = "ID of this project"
}

output "project_name" {
    value = var.project_name
    description = "Base project ID (can be used to create resource names)"
}

output "project_service_account_email" {
    value = module.project.service_account_email
    description = "Project service account"
}

output "deploy_service_account_email" {
    value = google_service_account.deploy.email
    description = "Service account for deploying to the project"
}

output "tester_service_account_email" {
    value = google_service_account.tester.email
    description = "Service account for running tests"
}


output "docker_repository_namespace" {
    value = "${google_artifact_registry_repository.docker_repo.location}-docker.pkg.dev/${module.project.project_id}/${google_artifact_registry_repository.docker_repo.name}"
}

output "build_service_account_email" {
    value = google_service_account.build.email
}

output "github_identity_pool_provider_name" {
    value = google_iam_workload_identity_pool_provider.github.name
}

output "log_bucket_url" {
    value = google_storage_bucket.logs.name
}
