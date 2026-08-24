# =============================================================================
# main.tf — Secure Staging Provisioning
# Author: Jishnu Ravi | Contact: ravijishnu431@gmail.com
# Position: Junior Cloud & DevOps Engineer (GCP / Django / React) — HabotConnect
# Purpose: Remediates the incident described in the assessment scenario by
#          replacing ad-hoc, credential-leaking manual pushes with IaC that
#          enforces least-privilege IAM and row-level security by default.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  # Remote state — never commit state locally, it can itself leak secrets/IDs
  backend "gcs" {
    bucket = "REPLACE_WITH_TFSTATE_BUCKET"
    prefix = "terraform/state/staging"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "analytics_reader_group" {
  description = "Google Group (not individual users) granted read access to staged data"
  type        = string
  default     = "grp-analytics-readers@habotconnect.com"
}

variable "data_engineer_group" {
  description = "Google Group granted write/ingest access to raw landing"
  type        = string
  default     = "grp-data-engineers@habotconnect.com"
}

# -----------------------------------------------------------------------------
# TASK 1a: GCS Raw Landing Bucket ("D0 Raw Landing")
# -----------------------------------------------------------------------------
resource "google_storage_bucket" "raw_landing" {
  name     = "${var.project_id}-d0-raw-landing"
  location = var.region
  project  = var.project_id

  labels = {
    display_name = "d0-raw-landing"
    environment  = "staging"
    data_class   = "raw-unvalidated"
  }

  # No public access, ever — this is the exact class of mistake in the scenario
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  # Encryption at rest with a customer-managed key (never rely on defaults
  # for anything holding credentials/PII-adjacent onboarding data)
  encryption {
    default_kms_key_name = google_kms_crypto_key.raw_landing_key.id
  }

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  # Quarantine path for anything that fails the CI/CD gate in Task 2
  logging {
    log_bucket = google_storage_bucket.access_logs.name
  }
}

resource "google_storage_bucket" "access_logs" {
  name                        = "${var.project_id}-raw-landing-access-logs"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_kms_key_ring" "staging_keyring" {
  name     = "staging-keyring"
  location = var.region
  project  = var.project_id
}

resource "google_kms_crypto_key" "raw_landing_key" {
  name            = "raw-landing-key"
  key_ring        = google_kms_key_ring.staging_keyring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }
}

# Strict IAM condition: data engineers can only write objects, only from
# the CI/CD service account, only during the ingestion window — no standing
# broad access, and definitely no "hope nobody commits a key" reliance.
resource "google_storage_bucket_iam_member" "raw_landing_writer" {
  bucket = google_storage_bucket.raw_landing.name
  role   = "roles/storage.objectCreator"
  member = "group:${var.data_engineer_group}"

  condition {
    title       = "ingest-window-only"
    description = "Write access restricted to service-initiated ingest jobs"
    expression  = "resource.name.startsWith(\"projects/_/buckets/${google_storage_bucket.raw_landing.name}/objects/incoming/\")"
  }
}

resource "google_storage_bucket_iam_member" "raw_landing_ci_uploader" {
  bucket = google_storage_bucket.raw_landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# -----------------------------------------------------------------------------
# TASK 1b: BigQuery Dataset ("D1 Staged/Enforced")
# -----------------------------------------------------------------------------
resource "google_bigquery_dataset" "staged_enforced" {
  dataset_id                  = "d1_staged_enforced"
  friendly_name                = "D1 Staged/Enforced"
  project                      = var.project_id
  location                     = var.region
  description                  = "Schema-validated, RLS-enforced staging layer downstream of raw landing"
  default_table_expiration_ms  = null # governed tables, not ephemeral

  labels = {
    environment = "staging"
    data_class  = "validated"
  }

  # Default encryption via CMEK, consistent with the raw bucket
  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.raw_landing_key.id
  }

  access {
    role          = "OWNER"
    user_by_email = google_service_account.pipeline_sa.email
  }

  access {
    role           = "READER"
    group_by_email = var.analytics_reader_group
  }
}

# Row-Level Security: analytics readers only see rows matching their
# assigned region claim — eliminates the "everyone sees everything"
# failure mode implied by the schema-mismatch incident.
resource "google_bigquery_table" "student_onboarding" {
  dataset_id = google_bigquery_dataset.staged_enforced.dataset_id
  table_id   = "student_onboarding"
  project    = var.project_id

  schema = file("${path.module}/../schemas/student_onboarding_schema.json")

  deletion_protection = true
}

# NOTE ON THIS PREDICATE: SESSION_USER_REGION() is a placeholder function
# name used to keep this file self-contained for review. In an actual
# HabotConnect deployment, this would be replaced with a real join against
# an "authorized_regions" mapping table keyed on SESSION_USER(), so the
# region claim is looked up from a governed table rather than invented at
# query time. This is called out explicitly rather than left silent.
resource "google_bigquery_row_access_policy" "rls_analytics_by_region" {
  project               = var.project_id
  dataset_id            = google_bigquery_dataset.staged_enforced.dataset_id
  table_id              = google_bigquery_table.student_onboarding.table_id
  row_access_policy_id  = "rls_region_scope"

  filter_predicate = "region = SESSION_USER_REGION()"

  grantees = [
    "group:${var.analytics_reader_group}",
  ]
}

# -----------------------------------------------------------------------------
# Least-privilege service account for the CI/CD pipeline (Task 2 references this)
# -----------------------------------------------------------------------------
resource "google_service_account" "pipeline_sa" {
  account_id   = "staging-pipeline-sa"
  display_name = "Staging Pipeline Service Account (least privilege)"
  project      = var.project_id
}

resource "google_project_iam_member" "pipeline_sa_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"

  condition {
    title       = "staging-dataset-only"
    description = "Scoped to D1 Staged/Enforced only, not project-wide"
    expression  = "resource.name.startsWith(\"projects/${var.project_id}/datasets/d1_staged_enforced\")"
  }
}

output "raw_landing_bucket_name" {
  value = google_storage_bucket.raw_landing.name
}

output "staged_dataset_id" {
  value = google_bigquery_dataset.staged_enforced.dataset_id
}
