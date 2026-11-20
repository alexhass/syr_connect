---
description: Version of the integration and minimum version of Home Assistant
applyTo: "{custom_components/syr_connect/manifest.json,hacs.json,REQUIREMENTS.md,requirements-dev.txt}"
---

# Releases

- The version of the integration is only in `version` of `custom_components/syr_connect/manifest.json`. `helpers.integration.get_integration_version()` reads it from there, for example for the User-Agent. Do not add it anywhere else.
- The maintainer decides which part of the version is raised for a release. A major version marks an integration that was largely written anew: 2.0.0 came with most of the code reworked and a new minimum version of Home Assistant.
- The minimum version of Home Assistant (`homeassistant` in `hacs.json`) is only raised when the code needs it: an API, a constant or a text of Home Assistant or its frontend that older versions do not have. Examples are `UnitOfRatio.PERCENTAGE` and the texts of the reauth and reconfigure aborts of the `homeassistant` domain (2026.10). A new release of Home Assistant alone is no reason.
- When the minimum version is raised, `REQUIREMENTS.md` is changed with it, and `homeassistant` in `requirements-dev.txt` must not be older than it.
