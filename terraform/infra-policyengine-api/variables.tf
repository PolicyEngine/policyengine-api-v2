variable "project_id" {
    type = string
    description = "project to instantiate the household api service in"
}

variable "container_image" {
    type = string
    description = "container image to deploy to the household api service"
}

variable "is_prod" {
    type = bool
    description = "should we deploy for production scale?"
}