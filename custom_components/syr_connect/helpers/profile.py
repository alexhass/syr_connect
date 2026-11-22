"""Device profile lookups: the entity allowlists of a model."""

from collections.abc import Set as AbstractSet
import logging

from ..aiosyrconnect import SyrConnectStatus
from ..models import SyrConnectModel

_LOGGER = logging.getLogger(__name__)


def get_model_supported_keys(
    model_info: SyrConnectModel, platform: str, global_supported_keys: set[str]
) -> set[str]:
    """Return the supported-keys allowlist for a platform, scoped to the detected model.

    If the detected model has a `device_profile` (from a `devices/<name>.py` file,
    see `models.MODELS`), its allowlist for the platform is used as a
    POSITIVE, device-specific allowlist instead of `global_supported_keys`.
    Rebranded variants of the same hardware share one profile.
    This is deliberately an allowlist, not an exclusion list — the global
    allowlists of the platform modules cover ~90 different models, and new/unexpected keys can
    show up in any device's API response at any time, so only explicitly
    confirmed keys are trusted per device. Falls back to `global_supported_keys`
    unchanged when the model has no profile, or its profile has no allowlist for
    this platform (an explicit empty set is honored as "no entities of this
    platform for this model", not a fallback trigger).

    Args:
        model_info: Result of `models.detect_model()`.
        platform: Entity domain string (e.g. "sensor", "select", "switch"); the name
            of a `SyrConnectDeviceProfile` allowlist field.
        global_supported_keys: The platform's full/default allowlist.

    Returns:
        The effective allowlist to use for this device.
    """
    profile = model_info.device_profile
    if profile is None:
        return global_supported_keys
    # No default: a platform without a profile field is a programming error.
    device_keys: AbstractSet[str] | None = getattr(profile, platform)
    # None means "not defined" -> fall back. An explicit empty set is a valid
    # override meaning "this model has none of this platform's entities".
    if device_keys is None:
        return global_supported_keys
    return set(device_keys)


def get_cartridge_entity_keys(
    model: SyrConnectModel, status: SyrConnectStatus, supported_keys: AbstractSet[str]
) -> set[str]:
    """Return the cartridge keys that become entities for the device.

    Args:
        model: Detected model of the device.
        status: The flattened device status.
        supported_keys: The keys the model lists for the platform.

    Returns:
        The keys of the reported cartridge type and size (see
        `reported_cartridge_keys()` of the signature) that the model lists and that
        have a value.
    """
    return {
        key
        for key in model.reported_cartridge_keys(status)
        if key in supported_keys and status.get(key) not in (None, "")
    }
