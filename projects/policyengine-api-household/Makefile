TAG?=desktop
REPO?=api-v2
REGION?=us-central1
deploy:
	rm -rf build/staging
	mkdir -p build/staging/libs
	cp -R ../../libs/* build/staging/libs/
	gcloud builds submit --region=us-west2 --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/policyengine-api-household:${TAG}