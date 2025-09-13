# Terraform/backend.tf
# Remote backend for shared Terraform state
terraform {
  backend "s3" {
    bucket         = "max-tfstate-bucket"            # <-- PUT bootstrap output here
    key            = "eks/dadjokes/terraform.tfstate"
    region         = "il-central-1"
    dynamodb_table = "tf-locks"                      # <-- PUT bootstrap output here
    encrypt        = true
  }
}
