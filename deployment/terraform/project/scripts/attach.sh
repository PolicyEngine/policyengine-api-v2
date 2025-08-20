#!/bin/bash

#Get the project id we're currently configured to use
project_id=$(gcloud config get-value project)

stage="UNKNOWN"
echo "Project id is: ${project_id}"

#Infer the stage from the project id
case "$project_id" in
    prod*)
        echo "stage is prod"
        stage="prod"
        ;;
    beta*)
        echo "stage is beta"
        stage="beta"
        ;;
    desk-*)
	echo "stage is desktop"
        # Extract desk-username from the beginning
        stage="${project_id%-*}"
        ;;
    *)
        echo "Unable to determine stage from project name"
        exit 1
        ;;
esac

# TODO: handle desktop setup.
is_desktop=false

is_prod=false
if [ "$stage" == "prod" ]; then
    is_prod=true
fi

files=("terraform.tfstate" "backend.tf" "../apply.tfvars" "../backend.tfvars")

# Check each file
for file in "${files[@]}"; do
    if [ -e "$file" ]; then
        echo "Error: $file already exists. You cannot manage two bootstrapped projects in the same repo. Chickening out."
        exit 1
    fi
done


set -e

#pull all the config values from gcloud
org_id=$(gcloud projects describe $(gcloud config get-value project) --format="value(parent.id)")
echo "org_id is ${org_id}"
billing_account=$(gcloud billing projects describe $(gcloud config get-value project) --format="value(billingAccountName)" | cut -d'/' -f2)
echo "billing_account is ${billing_account}"
project_bucket="${project_id}-state"
echo "project bucket is ${project_bucket}"
repo_owner_name=$(git remote get-url origin | sed -n 's/.*[\/:]\([^\/]*\)\/[^\/]*\.git$/\1/p')
echo "repo owner name is ${repo_owner_name}"
github_repo_owner_id=$(curl -s "https://api.github.com/users/$repo_owner_name" | jq -r '.id')
echo "repo_owner_id is ${github_repo_owner_id}"
github_repo=$(git remote get-url origin | sed 's/.*[\/:]\([^\/]*\/[^\/]*\)\.git$/\1/')
echo "repo is ${github_repo}"
echo " (OPTIONALLY) Please go into the console and create a slack notification channel. Write down the display name. It's usually Slack Notifications"
read -p "Enter notification channel display name (LEAVE EMPTY FOR NONE):" slack_notification_channel_name

echo "Creating ../.bootstrap_settings files to support other make commands."

mkdir ../.bootstrap_settings

echo "Creating apply.tfvars which is used to load terraform variables for future terraform apply commands"
cat > ../.bootstrap_settings/apply.tfvars << EOF
org_id           = "${org_id}"
billing_account  = "${billing_account}"
stage            = "${stage}"
project_id       = "${project_id}"
is_prod          = ${is_prod}
github_repo_owner_id = "${github_repo_owner_id}"
github_repo          = "${github_repo}"
slack_notification_channel_name = "${slack_notification_channel_name}"
EOF

echo "Creating backend.tfvars which is used to configure the backend.tf settings when using terraform init"
cat > ../.bootstrap_settings/backend.tfvars << EOF
bucket = "${project_bucket}"
EOF

echo "Creating project.env for Makefiles to load the project id of the created project."
cat > ../.bootstrap_settings/project.env << EOF
PROJECT_ID=${project_id}
EOF

echo "Creating backend.tf"
cat > backend.tf << EOF
terraform {
  backend "gcs" {
    bucket = "${project_bucket}"
    prefix = "terraform/desktop/policyengine-api"
  }
}
EOF
