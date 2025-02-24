terraform {
  backend "gcs" {
    bucket = "nikhil-api-v2-dc52-state"
    prefix = "terraform/project"
  }
}
