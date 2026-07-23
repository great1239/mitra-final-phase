# Portable Deployment Validation

## File: `.github/workflows/deployment-parity.yml`

**Sprint change:** Added repository and hosted parity automation.

**Purpose:** Runs the same runtime validators after deployment, on demand, and
daily instead of relying on a developer workstation.

**Why modified:** Production regressions must be detected from the hosted
network and exact deployed commit.

**Key implementation areas:** Python 3.12 clean install, full regression suite,
hosted surface validation, canonical ecosystem execution, and SHA matching.

**Review focus:** Hosted acceptance is a separate job and cannot be replaced by
unit-test success.

**Related tests:** Workflow YAML parsing, regression suite, and live validators.
