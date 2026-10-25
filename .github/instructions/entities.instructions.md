---
description: Entity, unique_id and entity registry rules for the syr_connect platforms
applyTo: "custom_components/syr_connect/*.py"
---

# Entities and registry

- Build every `unique_id` with `helpers.build_unique_id(entry_id, device_id, key)`. The same device can be reachable from several config entries.
- `entry_id` is an uppercase ULID. Never call `.lower()` on the whole `unique_id`. Lowercase only the `device_id` and key parts before passing them in, otherwise the id no longer matches the migrated registry entry and a duplicate entity appears.
- Do not change the `entity_id` format. Home Assistant resolves collisions itself.
- Every entity registry removal (`registry_cleanup()` and ad-hoc removal loops) must be limited to entities owned by the current config entry. Otherwise one hub deletes the entities of another hub on startup. Look them up with `er.async_entries_for_config_entry(registry, coordinator.entry_id)` (indexed) or by unique_id with `find_entity_id()`, never by scanning `registry.entities`. Without an `entry_id` nothing is removed.
- Platforms create their entities per device through `entity.async_add_device_entities`, so a device that appears after the setup (new in the account, or without status at the setup) gets its entities with the next coordinator update. Do not loop over the devices once in `async_setup_entry`.
- Entities that do not apply to a device are added or removed (registry removal plus `async_add_entities`), not just marked unavailable. `available` is only for offline devices.
- Never use truthiness for values that can legitimately be `0` or an empty collection. Use `is None` / `is not None` (for example `raw = str(v) if v is not None else ""`).
- Every platform must honor the per-model allowlists, see `devices.instructions.md`. An entity-creation loop that only checks `key in status` is a bug.
- Firmware update entity (`update.py`): `entity_category` is `DIAGNOSTIC`, there is no `entity_picture` override and `INSTALL` sends `setUPG` with an empty value (see `docs/syrconnect-protocol.md`), the progress lasts until getNOT reports "04" or the timeout expires. Do not change these without being asked, they were decided deliberately.
