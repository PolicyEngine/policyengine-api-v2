variable "project_id" {
  description = "The GCP project to deploy to"
  type        = string
}

variable "region" {
  description = "The region to deploy the cloud run service to."
  type        = string
}

variable "docker_repo" {
  description = "The name of the repo to get the image from"
  type = string
}

variable "container_tag" {
  description = "The container image tag to deploy."
  type        = string
}

variable limits {
  type = object({
    cpu    = number
    memory = string
  })
}

variable min_instance_count {
  description = "The minimum number of instances to keep 'hot' regardless of requests"
  type = number
}

variable max_instance_count {
  description = "The maximum number of instances to allow;"
  type = number
  default = 1
}

variable max_instance_request_concurrency {
  description = "How many requests can a single container handle at once"
  type = number
}

variable request_based_billing {
  description = "Whether to use request-based billing for the Cloud Run service"
  type        = bool
  default     = false
}

variable "uptime_timeout" {
  type = string
  description = "number of seconds to wait for the uptime check response before failing"
}


variable "environment_secrets" {
  description = "Map of environment variable names to their corresponding secret IDs in Google Secret Manager"
  type = map(string)
  default = {}
}

variable "env" {
  description = "Environment variables directly assigned to string values"
  type = map(string)
  default = {}
}

variable "timeout" {
  description = "Max time a container can take to respond to a request up to 1 hour"
  type = string
}

variable "description" {
  type = string
}

variable "name" {
  type = string
}

variable "slack_notification_channel_name" {
  type = string
  default = ""
}

variable "commit_url" {
  type = string
  description = "URL of the commit this deployment is associated with"
}

variable "members_can_invoke" {
  type = list(string)
  description = "entities to add to the invoke policy for this service"
  default = []
}

variable "service_roles" {
  type = list(string)
  description = "roles to give the service account for this clodurun service"
  default = []
}

variable "enable_uptime_check" {
  type = bool
  description = "Should this autogenerate an uptime check for the cloudrun service"
}
