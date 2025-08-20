terraform {
  backend "gcs" {
    bucket = "beta-api-v2-1b3f-state"
    prefix = "infra"
  }
}
