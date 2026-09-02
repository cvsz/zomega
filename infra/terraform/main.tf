terraform {
  required_version = ">= 1.6.0"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "omega_image" {
  type = string
}

resource "docker_network" "omega" {
  name = "omega"
}

resource "docker_volume" "postgres" {
  name = "omega-postgres"
}

resource "docker_volume" "redis" {
  name = "omega-redis"
}

output "network_name" {
  value = docker_network.omega.name
}
