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

variable "zomega_image" {
  type = string
}

resource "docker_network" "zomega" {
  name = "zomega"
}

resource "docker_volume" "postgres" {
  name = "zomega-postgres"
}

resource "docker_volume" "redis" {
  name = "zomega-redis"
}

output "network_name" {
  value = docker_network.zomega.name
}
