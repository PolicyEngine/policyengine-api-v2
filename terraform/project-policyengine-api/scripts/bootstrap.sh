#!/bin/bash

# Check if stage argument is provided
if [ $# -ne 1 ]; then
    echo "Error: Stage argument is required"
    echo "Usage: $0 <stage>"
    echo "Valid stages: beta, prod, desktop"
    exit 1
fi

stage=$1

# Validate stage argument
if [[ ! "$stage" =~ ^(beta|prod|desktop)$ ]]; then
    echo "Error: Invalid stage '$stage'"
    echo "Valid stages: beta, prod, desktop"
    exit 1
fi

is_desktop=false

# Set stage to current user if desktop
if [ "$stage" == "desktop" ]; then
    read -p "Enter username (used for stage): " username
    stage="desk-$username"
    is_desktop=true
fi

is_prod=false
if [ "$stage" == "prod" ]; then
    is_prod=true
fi

# Chicken out if it looks like we've already bootstrapped....
files=("terraform.tfstate" "backend.tf" "../apply.tfvars" "../backend.tfvars")

# Check each file
for file in "${files[@]}"; do
    if [ -e "$file" ]; then
        echo "Error: $file already exists. You cannot manage two bootstrapped projects in the same repo. Chickening out."
        exit 1
    fi
done


set -e

# Prompt for values
read -p "Enter org_id: " org_id
read -p "Enter billing_account: " billing_account

github_repo_owner_id="NOT_USED_FOR_DESKTOP"
github_repo="NOT_USED_FOR_DESKTOP"
if [ "$is_desktop" == "false" ]; then
    read -p "Enter GitHub repo owner ID: " github_repo_owner_id
    read -p "Enter GitHub repo name: " github_repo
fi

terraform init
terraform apply -var "org_id=${org_id}" -var "billing_account=${billing_account}"\
    -var "stage=${stage}" \
    -var "github_repo_owner_id=${github_repo_owner_id}" -var "github_repo=${github_repo}"
terraform init -migrate-state

echo " (OPTIONALLY) Please go into the console and create a slack notification channel. Write down the display name"
read -p "Enter notification channel display name (LEAVE EMPTY FOR NONE):" slack_notification_channel_name


project_id=$(terraform output -raw project_id)
project_bucket=$(terraform output -raw project_bucket)

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
