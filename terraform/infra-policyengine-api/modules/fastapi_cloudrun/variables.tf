variable "is_prod" {
  description = "Whether this is a production deployment"
  type        = bool
}

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

variable request_based_billing {
  description = "Whether to use request-based billing for the Cloud Run service"
  type        = bool
  default     = false
}

variable max_instance_request_concurrency {
  description = "Maximum number of requests to allow in a single instance"
  type        = number
  default     = 80
}

variable "environment_secrets" {
  description = "Map of environment variable names to their corresponding secret IDs in Google Secret Manager"
  type = map(string)
  default = {}
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
