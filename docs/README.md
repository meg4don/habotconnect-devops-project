# HabotConnect Hiring Project Submission

**Full Name:** Jishnu Ravi
**Contact Information:** ravijishnu431@gmail.com | 8111940958 (Alternate: 8943105754)
**Position:** Junior Cloud & DevOps Engineer (GCP / Django / React)
**Submission Date:** [Date]

---

## Folder Structure

```
habotconnect-project/
├── terraform/
│   └── main.tf                          # Task 1: GCS + BigQuery, IAM, RLS
├── ci-cd/
│   └── .github/workflows/
│       └── build-gate.yml               # Task 2: Fail-Closed Poka-Yoke gate
├── django/
│   ├── dcyn_library.py                  # Task 3: DCYN validation library
│   └── serializers.py                   # Task 3: DRF model serializer
├── schemas/
│   ├── student_onboarding_schema.json   # BigQuery table schema (used by Task 1)
│   ├── sample_onboarding_payload.json   # Example incoming JSON payload
│   └── schema_field_mapping.xlsx        # Field-by-field mapping spreadsheet
└── docs/
    └── README.md                        # This file
```

## Task 1 — Terraform Secure Staging Provisioning

`terraform/main.tf` provisions:
- A GCS bucket (`D0 Raw Landing`) with uniform bucket-level access, enforced public access prevention, customer-managed encryption (CMEK), versioning, and IAM conditions scoping write access to a defined ingest path.
- A BigQuery dataset (`D1 Staged/Enforced`) with CMEK encryption and a Row-Level Security policy scoping analytics readers to their assigned region.

**How to validate without a live deployment:**
```bash
terraform init
terraform validate
terraform plan -var="project_id=YOUR_PROJECT_ID"
```
`terraform plan` is sufficient evidence of correctness; a live `apply` was not performed for this submission to avoid unnecessary cloud spend, and can be run on request during the interview if required.

**Documented assumption:** the Row-Level Security filter predicate uses a placeholder function name, `SESSION_USER_REGION()`, called out directly in the file's comments. In a production HabotConnect deployment this would be replaced with a join against a governed `authorized_regions` mapping table keyed on `SESSION_USER()`.

## Task 2 — Poka-Yoke Automated CI/CD Build Gate

`ci-cd/.github/workflows/build-gate.yml` runs on every push and pull request, executing formatting checks (Black), linting (Flake8), and secret scanning (Gitleaks plus a custom regex sweep for common credential shapes). Any failure in either the lint or secret-scan job triggers the `quarantine` job, which explicitly fails the pipeline and blocks any downstream deployment step.

**Proof of Fail-Closed behavior:** a throwaway commit containing a fake hardcoded API key and a formatting violation was pushed to a public repository running this workflow. The resulting failed run is included as a screenshot in the accompanying slide presentation, alongside a subsequent passing run after the violations were removed.

## Task 3 — Schema Mapping & DCYN Validation

`django/dcyn_library.py` deconstructs the incoming student onboarding payload into individual, auditable Yes/No checks, each returning a `DCYNResult` with a stated reason rather than a bare boolean, so no result is unexplained.

`django/serializers.py` implements the same rules structurally at the Django REST Framework layer, using exact field types, regex patterns, and value ranges rather than open-ended text fields — no field relies on a human reviewer's judgment.

`schemas/schema_field_mapping.xlsx` maps every field from the incoming JSON payload through its DCYN check and serializer rule to its final column in the `D1 Staged/Enforced` BigQuery dataset. Wrap Text is enabled throughout, and all descriptions use full words rather than abbreviations or placeholders, per the submission requirements.

## Notes on Scope

This submission focuses on the three tasks as specified. The assessment table's mention of "GCP App Engine" is not reflected in the Task 1 instructions (which specify only a GCS bucket and a BigQuery dataset), so no App Engine resources were provisioned in order to keep the submission precisely scoped to what was asked.
