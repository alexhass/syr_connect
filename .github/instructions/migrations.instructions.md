---
description: Migrations of config entries and of the entity registry
applyTo: "custom_components/syr_connect/{__init__.py,config_flow.py,migrations.py}"
---

# Migrations

- A migration is needed when stored data no longer fits the code: the data or the `unique_id` of a config entry, the format of entity unique IDs (see `entities.instructions.md`), an entity that moves to another platform, or a unit override stored in the entity registry. Without it, the entities of existing users are duplicated or lose their history and customizations.
- No migration is needed for an entity whose key is dropped from the allowlists: `registry_cleanup()` removes it.
- A migration raises `ConfigFlow.VERSION` in `config_flow.py` by one. `MINOR_VERSION` is not used.
- The code of a step is a function `v<N>_to_v<N+1>_<what>` in `migrations.py`. It either fixes the registry (`(hass, entry) -> None`) or returns the update kwargs of the entry (`data`, `unique_id`, `"version": N + 1`), or `None` when the entry needs no change.
- Every step is one `_SyrConnectMigrationStep` at the end of `_SYR_CONNECT_MIGRATION_STEPS` in `__init__.py`, with `from_version`, a `description` for the log and exactly one of `fix_registry` and `update_kwargs`. `async_migrate_entry` raises the version of a step without update kwargs itself. `test_migration_steps_cover_every_version` checks that there is one step per version.
- Existing steps are never changed or removed. An entry of any older version runs all steps from its version on.
- A step leaves entries that are already migrated, or that it does not apply to (cloud or local entries), unchanged.
- A step that needs the device raises `ConfigEntryNotReady` while it cannot be reached, so Home Assistant retries the migration, and `ConfigEntryError` when the result cannot be determined (see v8 -> v9).
- A step that would give an entry a `unique_id` another entry already has keeps the old `unique_id` and logs a warning (see v10 -> v11).
- Every step has tests in `tests/test_migrations.py`, named `test_v<N>_to_v<N+1>_<case>`: the migrated case and every case the step leaves unchanged.
