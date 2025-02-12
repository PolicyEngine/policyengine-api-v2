fastapi app that only includes the household API routes.


to run dev mode do
``cd src/policyengine_api_household``
``fastapi dev``


To deploy to dev account 
1. Make sure your project is able to build/deploy following the start of [these instructions](https://cloud.google.com/build/docs/build-push-docker-image)
1. Create a repository (api-v2 by default)
1. run ``make deploy PROJECT_ID=<your project id>``