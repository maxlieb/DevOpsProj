# Terraform/main.tf

terraform {
  required_version = ">= 1.0"

  # NOTE: Remote backend is defined in Terraform/backend.tf
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# Get available AZs
data "aws_availability_zones" "available" {}

# EKS Cluster with everything included
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"

  # Do NOT auto-grant cluster admin to the "creator" principal.
  # We manage access explicitly via 'access_entries'.
  enable_cluster_creator_admin_permissions = false

  # Explicit cluster access entries
  access_entries = {
    # GitHub Actions OIDC role (used by your workflow to run kubectl/apply)
    gha = {
      principal_arn = "arn:aws:iam::863518423554:role/GHA-Terraform-EKS"
      policy_associations = [{
        policy_arn  = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
        access_scope = { type = "cluster" }
      }]
    }

    # Your personal IAM user (so you have kubectl access locally)
    admin = {
      principal_arn = "arn:aws:iam::863518423554:user/max"
      policy_associations = [{
        policy_arn  = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
        access_scope = { type = "cluster" }
      }]
    }
  }

  # Simple cluster configuration
  cluster_endpoint_public_access = true

  # Essential add-ons only
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }

  # Single managed node group
  eks_managed_node_groups = {
    default = {
      instance_types = ["t3.small"]

      min_size     = 0
      max_size     = 2
      desired_size = 1

      disk_size = 20
    }
  }
}

# Minimal VPC setup
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# Simple outputs
output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "update_kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${var.cluster_name}"
}
