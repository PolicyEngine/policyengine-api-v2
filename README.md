DO NOT COMMIT. THIS IS A TEST TO SEE WHY GITHUb ACTIONS ARE NOT TRIGGERING.


Monorepo containing all the libraries, applications, terraform and github actions required to build/test/deploy/release the PolicyEngine api V2.

# Local Development Quick Start
* [install poetry](https://python-poetry.org/docs/#installation)
* ``make build`` - install and pytest all libraries and projects.

# Cloud Development Quick Start
__NOTE: MOST development should be possible locally. Deployment is slow and hard to debug. Change with caution__

* One time setup - this will create a new project in your GCP account you can deploy the api to.
  * Create a gcp account _with organization_
  * authenticate with gcloud as a user with permission to create projects.
  * Have your organization ID and billing account number handy.
  * ``cd terraform/infra-policyengine-api && make bootstrap``
  * You should now have a terraform/.bootstrap_settings folder containing your project settings.
* build the api docker image
  * ``cd projects/policyengine-api-full && make deploy``
  * There should now be a new hash under the tag "desktop" in the project artifact repository.
* deploy to the cloud
  * ``cd terraform/project-policyengine-api-full && make deploy``
  * The cloudrun service should now be running using the latest image version of the tag "deksop" from your project artifact respository

# Github Deploy to Cloud Quick Start

__checkout a clean version of the repository__ you cannot bootstrap more than one project 
in a workspace at a time.

* bootstrap the beta project
  * have your github repo owner id and repo (i.e. org/repo) ready
  * have your GCP organization id and billing account number ready
  * log into your gcp account via gcloud as a user able to create projects.
  * ``cd terraform/project-poicyengine-api && make bootstrap_beta``
* configure github
  * create a new environment in your github repo settings called "beta" and, using the ouput of the bootstrap, configure the following values
    * REGION (generally us-central1)
    * PROJECT_ID (in the output of the bootstrap target)
    * _GITHUB_IDENTITY_POOL_PROVIDER_NAME (in the output of the bootstrap build target)
    * ORG_ID
    * BILLING_ACCOUNT
