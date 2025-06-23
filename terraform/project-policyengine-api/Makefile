
bootstrap:
	scripts/bootstrap.sh desktop

attach:
	scripts/attach.sh
	terraform init

detach:
	rm -f backend.tf
	rm -rf ../.bootstrap_settings
	rm -rf .terraform
	rm -rf terraform.tfstate*

bootstrap_beta:
	scripts/bootstrap.sh beta

bootstrap_prod:
	scripts/bootstrap.sh prod

deploy:
	@echo "Attempting to deploy project using bootstrap settings in ../.bootstrap_settings/apply.tfvars"
	terraform apply --var-file=../.bootstrap_settings/apply.tfvars

destroy:
	terraform plan -destroy --var-file=../.bootstrap_settings/apply.tfvars
	@echo "In order to _actually_ destroy the resources please MAKE SURE THIS IS NOT A PRODUCTION ACCOUNT and run: terraform destroy --var-file=../.bootstrap_settings/apply.tfvars"
