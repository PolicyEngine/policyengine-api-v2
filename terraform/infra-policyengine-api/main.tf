locals {
    is_prod = var.is_prod
    # Assumption from cost estimate. May need to tweak based on real performance.
    max_instance_request_concurrency = local.is_prod ? 80 : null
    # API is reachable if production otherwise internal-only.
    members = local.is_prod ? ["allUsers"] : []
    # keep one instance running at all times in production for responsiveness.
    # in other environments don't waste the money
    service_scaling = local.is_prod ? {
        min_instance_count = 1
        max_instance_count = 10 # This seems like more than enough (800 concurrent requests)
    } : {
        max_instance_count = 1
    }

    # minimum instance specs only apply in production
    cpu_limit = local.is_prod ? "2" : null
    memory_limit = local.is_prod ? "1024Mi" : null

    service_name = "household-api"
}

# https://github.com/GoogleCloudPlatform/terraform-google-cloud-run/tree/main/modules/v2
module "cloud_run_v2" {
  source  = "GoogleCloudPlatform/cloud-run/google//modules/v2"
  version = "~> 0.16"

  service_name = local.service_name
  project_id   = var.project_id
  location     = "us-central1"

  cloud_run_deletion_protection = false

  description = "PolicyEngine Household API"

  max_instance_request_concurrency =  local.max_instance_request_concurrency
  containers = [
    {
      container_image = var.container_image
      limits = {
        # as per the cost estimate we did for APIs.
        cpu    = local.cpu_limit
        memory = local.memory_limit
      }
    }
  ]
}