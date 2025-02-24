variable "project_id" {
    type = string
    description = "project to instantiate the household api service in"
}

variable "container_tag" {
    type = string
}

variable "region" {
    type = string
    default = "us-central1"
}

variable "is_prod" {
    type = bool
    description = "should we deploy for production scale?"
}
