output "full_api_url" {
  value = module.cloud_run_full_api.uri
}

output "simulation_api_url" {
  value = module.cloud_run_simulation_api.uri
}

output "tagger_api_url" {
  value = module.cloud_run_tagger_api.uri
}

output "workflow_id" {
  value = google_workflows_workflow.simulation_workflow.id
}

output "workflow_service_account_email" {
  value = google_service_account.workflow_sa.email
  description = "Service account for running workflows"
}

output "release_metadata" {
  value = local.metadata
  description = "json blob that should be stored as metadata for this release of the api. Used to establish the right version of the cloudrun api for a given uk or us country package"
}

output "metadata_bucket_name" {
  value = google_storage_bucket.metadata.name
}
