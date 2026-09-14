from __future__ import annotations

import os
from enum import Enum


class ReleaseProfile(str, Enum):
    V1 = "V1"
    V1_5 = "V1_5"
    V2 = "V2"
    V2_5 = "V2_5"
    V3 = "V3"
    INTERNAL = "INTERNAL"


class Feature(str, Enum):
    CORE_JUDGMENT = "CORE_JUDGMENT"
    REEVALUATION = "REEVALUATION"
    PERMISSION_ACTION = "PERMISSION_ACTION"
    CONTEXTUAL_NUDGE = "CONTEXTUAL_NUDGE"
    RESPONSE_COMPOSER = "RESPONSE_COMPOSER"
    EXPLAIN_MODE = "EXPLAIN_MODE"
    LONG_TERM_ADAPTATION = "LONG_TERM_ADAPTATION"


_PROFILE_FEATURES: dict[ReleaseProfile, set[Feature]] = {
    ReleaseProfile.V1: {
        Feature.CORE_JUDGMENT,
        Feature.REEVALUATION,
    },
    ReleaseProfile.V1_5: {
        Feature.CORE_JUDGMENT,
        Feature.REEVALUATION,
        Feature.PERMISSION_ACTION,
    },
    ReleaseProfile.V2: {
        Feature.CORE_JUDGMENT,
        Feature.REEVALUATION,
        Feature.PERMISSION_ACTION,
        Feature.CONTEXTUAL_NUDGE,
        Feature.RESPONSE_COMPOSER,
    },
    ReleaseProfile.V2_5: {
        Feature.CORE_JUDGMENT,
        Feature.REEVALUATION,
        Feature.PERMISSION_ACTION,
        Feature.CONTEXTUAL_NUDGE,
        Feature.RESPONSE_COMPOSER,
        Feature.EXPLAIN_MODE,
    },
    ReleaseProfile.V3: set(Feature),
    ReleaseProfile.INTERNAL: set(Feature),
}


def get_release_profile() -> ReleaseProfile:
    raw = os.getenv("RELEASE_PROFILE", ReleaseProfile.V1.value).strip().upper()
    aliases = {
        "V1.5": "V1_5",
        "V2.5": "V2_5",
    }
    raw = aliases.get(raw, raw)
    try:
        return ReleaseProfile(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid RELEASE_PROFILE: {raw}") from exc


def enabled_features(profile: ReleaseProfile | None = None) -> set[Feature]:
    profile = profile or get_release_profile()
    return set(_PROFILE_FEATURES[profile])


def feature_enabled(feature: Feature, profile: ReleaseProfile | None = None) -> bool:
    return feature in enabled_features(profile)


def release_snapshot(profile: ReleaseProfile | None = None) -> dict:
    profile = profile or get_release_profile()
    enabled = enabled_features(profile)
    return {
        "profile": profile.value,
        "features": {
            feature.value: feature in enabled
            for feature in Feature
        },
    }
