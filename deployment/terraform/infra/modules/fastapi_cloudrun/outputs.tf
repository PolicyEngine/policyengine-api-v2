output "uri" {
    value = google_cloud_run_v2_service.api.uri
}

output "revision" {
    value = local.revision_name
}

output "location" {
    value = google_cloud_run_v2_service.api.location
}

output "name" {
    value = google_cloud_run_v2_service.api.name
}

output "project" {
    value = google_cloud_run_v2_service.api.project
}

output "sa_email" {
    value = google_service_account.api.email
}

output "sa_account_id" {
    value = google_service_account.api.unique_id
}
