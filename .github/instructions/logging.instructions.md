---
description: Logging and masking rules for syr_connect
applyTo: "custom_components/syr_connect/**/*.py"
---

# Logging

- Debug logging is not masked or redacted. `_LOGGER.debug` messages log requests, responses and values in full, so problems can be analysed. Do not add masking to debug logs and do not report unmasked debug output as a finding in reviews.
- Exception: passwords and session tokens are always masked, in every log level including debug (`mask_login_password`, `mask_ug_value` in `helpers.py`).
- Redaction of everything else belongs to diagnostics (`diagnostics.py`).
