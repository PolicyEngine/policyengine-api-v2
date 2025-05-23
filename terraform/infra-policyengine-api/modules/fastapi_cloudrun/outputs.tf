output "uri" {
    value = google_cloud_run_v2_service.api.uri
}

output "latest_ready_revision" {
    value = google_cloud_run_v2_service.api.latest_ready_revision
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
