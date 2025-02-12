# How to deploy
1. Install terraform
1. Make sure your user in GCP has permission to create project resources (TODO: What are those?)
1. Manually create a project and in that project
  1. create a bucket for storing terraform state.
  2. Enable artifact repository (for docker images)
  3. enable cloud run Admin API

1. copy backend.example.tfvars to backend.tfvars and set "bucket" to the bucket you have created. Leave the path. 
1. copy apply.example.tfvars to apply.tfvars and update the project ID to be the ID of the project above
1. use ``gcloud auth application-default login`` to auth as you
1. run ``make init`` the first time to initialize terraform state storage
1. run ``make deploy PROJECT_ID=<your project ID>`` to deploy.