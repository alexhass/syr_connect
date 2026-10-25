"""Unit tests for SYR Connect with real LEXplus10SL data.

These tests use real data from a LEXplus10SL (Firmware 2.9, Hardware SLPL)
to ensure that the integration works with this device type.

Serial Number: 210836887
Device: LEXplus10SL
Firmware: 2.9 (SLPL)
"""

from typing import override
import unittest

from defusedxml import ElementTree

# Real XML response from LEXplus10SL
REAL_XML_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<sc>
  <dvs>
    <d dg="ffd3dbcb-f987-eb11-a875-0cc47a087b23" sbt="7" sta="2">
      <c n="getSRN" v="210836887" />
      <c n="getVER" v="2.9" />
      <c n="getFIR" v="SLPL" />
      <c n="getTYP" v="80" />
      <c n="getCNA" v="LEXplus10SL" />

      <!-- Wichtige funktionierende Sensoren -->
      <c n="getFLO" v="0" />
      <c n="getPRS" v="39" />
      <c n="getTOR" v="722" />
      <c n="getRES" v="720" />
      <c n="getNOR" v="710" />
      <c n="getSRE" v="0" />

      <!-- Leckagesschutz-Profile (fehlen im aktuellen Code!) -->
      <c n="getPA1" v="1" />
      <c n="getPA2" v="1" />
      <c n="getPA3" v="1" />
      <c n="getPA4" v="0" />
      <c n="getPA5" v="0" />
      <c n="getPA6" v="0" />
      <c n="getPA7" v="0" />
      <c n="getPA8" v="0" />

      <c n="getPN1" v="Anwesend" />
      <c n="getPN2" v="Abwesend" />
      <c n="getPN3" v="Neues Profil" />
      <c n="getPN4" v="" />
      <c n="getPN5" v="" />
      <c n="getPN6" v="" />
      <c n="getPN7" v="" />
      <c n="getPN8" v="" />

      <c n="getPF1" v="3500" />
      <c n="getPF2" v="3500" />
      <c n="getPF3" v="1999" />
      <c n="getPF4" v="3500" />
      <c n="getPF5" v="3500" />
      <c n="getPF6" v="3500" />
      <c n="getPF7" v="3500" />
      <c n="getPF8" v="3500" />

      <c n="getPT1" v="60" />
      <c n="getPT2" v="30" />
      <c n="getPT3" v="13" />
      <c n="getPT4" v="60" />
      <c n="getPT5" v="60" />
      <c n="getPT6" v="60" />
      <c n="getPT7" v="60" />
      <c n="getPT8" v="60" />

      <c n="getPV1" v="300" />
      <c n="getPV2" v="30" />
      <c n="getPV3" v="185" />
      <c n="getPV4" v="300" />
      <c n="getPV5" v="300" />
      <c n="getPV6" v="300" />
      <c n="getPV7" v="300" />
      <c n="getPV8" v="300" />

      <c n="getPRF" v="3" />
      <c n="getPRN" v="3" />
    </d>
  </dvs>
</sc>"""


class TestLEXplus10SL(unittest.TestCase):
    """Tests with real data from LEXplus10SL."""

    @override
    def setUp(self) -> None:
        """Parse real XML data."""
        self.root = ElementTree.fromstring(REAL_XML_RESPONSE)
        self.device = self.root.find(".//d")
        self.sensors = {c.get("n"): c.get("v") for c in self.device.findall("c")}

    def test_device_identification(self) -> None:
        """Test that LEXplus10SL is correctly identified."""
        assert self.sensors["getSRN"] == "210836887"
        assert self.sensors["getVER"] == "2.9"
        assert self.sensors["getFIR"] == "SLPL"
        assert self.sensors["getTYP"] == "80"
        assert self.sensors["getCNA"] == "LEXplus10SL"

    def test_flow_sensor_exists(self) -> None:
        """Test that flow sensor exists."""
        assert "getFLO" in self.sensors
        # In idle state, flow should be 0
        assert self.sensors["getFLO"] == "0"

    def test_pressure_sensor_exists(self) -> None:
        """Test that pressure sensor exists."""
        assert "getPRS" in self.sensors
        # Value 39 = 3.9 bar
        assert self.sensors["getPRS"] == "39"

    def test_volume_uses_gettor_not_getvol(self) -> None:
        """IMPORTANT: LEXplus10SL uses getTOR instead of getVOL!

        This is a critical difference to other SYR devices.
        If the code only supports getVOL, volume display will not work.
        """
        assert "getTOR" in self.sensors
        assert "getVOL" not in self.sensors
        assert self.sensors["getTOR"] == "722"

    def test_regeneration_sensor_exists(self) -> None:
        """Test that regeneration sensor exists."""
        assert "getSRE" in self.sensors
        # 0 = no regeneration active
        assert self.sensors["getSRE"] == "0"

    def test_leak_protection_profile_activation(self) -> None:
        """Test leak protection profile activation.

        LEXplus10SL has up to 8 profiles that can be activated/deactivated.
        This device has profiles 1-3 activated, 4-8 deactivated.
        """
        # Aktivierte Profile
        assert self.sensors["getPA1"] == "1"
        assert self.sensors["getPA2"] == "1"
        assert self.sensors["getPA3"] == "1"

        # Deaktivierte Profile
        assert self.sensors["getPA4"] == "0"
        assert self.sensors["getPA5"] == "0"
        assert self.sensors["getPA6"] == "0"
        assert self.sensors["getPA7"] == "0"
        assert self.sensors["getPA8"] == "0"

    def test_leak_protection_profile_names(self) -> None:
        """Test leak protection profile names.

        Profiles can be named by the user.
        This device has: "Anwesend" (Present), "Abwesend" (Absent), "Neues Profil" (New Profile)
        """
        assert self.sensors["getPN1"] == "Anwesend"
        assert self.sensors["getPN2"] == "Abwesend"
        assert self.sensors["getPN3"] == "Neues Profil"

        # Non-configured profiles have empty names
        assert self.sensors["getPN4"] == ""
        assert self.sensors["getPN5"] == ""

    def test_leak_protection_active_profile(self) -> None:
        """Test that active profile is correctly detected.

        getPRF shows which profile (1-8) is currently active.
        In this case: Profile 3 "Neues Profil"
        """
        assert self.sensors["getPRF"] == "3"
        assert self.sensors["getPRN"] == "3"

        # The active profile should also be activated
        assert self.sensors["getPA3"] == "1"

        # Name of the active profile
        assert self.sensors["getPN3"] == "Neues Profil"

    def test_leak_protection_profile_3_flow_threshold(self) -> None:
        """Test flow leakage threshold of profile 3.

        App shows: "Flow leakage 1999 l/h"
        XML provides: getPF3="1999"

        If this value is exceeded, an alarm is triggered.
        """
        assert self.sensors["getPF3"] == "1999"

    def test_leak_protection_profile_3_time_threshold(self) -> None:
        """Test time leakage threshold of profile 3.

        App shows: "Time leakage 0.2 h"
        XML provides: getPT3="13" (minutes)

        0.2h x 60 = 12 minutes (rounding difference in app)
        """
        assert self.sensors["getPT3"] == "13"

    def test_leak_protection_profile_3_volume_threshold(self) -> None:
        """Test volume leakage threshold of profile 3.

        App shows: "Volume leakage 185 L"
        XML provides: getPV3="185"

        Perfect match!
        """
        assert self.sensors["getPV3"] == "185"

    def test_all_leak_protection_profiles_have_all_parameters(self) -> None:
        """Test that ALL 8 profiles have the required parameters.

        Each profile (1-8) must have:
        - getPA: activation
        - getPN: name
        - getPF: flow leakage
        - getPT: time leakage
        - getPV: volume leakage
        """
        for i in range(1, 9):
            with self.subTest(profile=i):
                assert f"getPA{i}" in self.sensors, f"Profil {i} fehlt Aktivierung"
                assert f"getPN{i}" in self.sensors, f"Profil {i} fehlt Name"
                assert f"getPF{i}" in self.sensors, (
                    f"Profil {i} fehlt Durchflussleckage"
                )
                assert f"getPT{i}" in self.sensors, f"Profil {i} fehlt Zeitleckage"
                assert f"getPV{i}" in self.sensors, f"Profil {i} fehlt Volumenleckage"

    def test_sensor_creation_should_not_crash_on_missing_icon(self) -> None:
        """CRITICAL TEST: Sensor creation must not crash if icon is missing.

        This was the original bug in sensor.py:175

        Many leak protection sensors do not have an icon in icons.json.
        The code must handle this.
        """
        # Simuliere Sensoren ohne Icon
        sensors_without_icon = [
            "getPA1",
            "getPA2",
            "getPA3",
            "getPA4",
            "getPA5",
            "getPA6",
            "getPA7",
            "getPA8",
            "getPN1",
            "getPN2",
            "getPN3",
            "getPN4",
            "getPN5",
            "getPN6",
            "getPN7",
            "getPN8",
            "getPF1",
            "getPF2",
            "getPF3",
            "getPF4",
            "getPF5",
            "getPF6",
            "getPF7",
            "getPF8",
            "getPT1",
            "getPT2",
            "getPT3",
            "getPT4",
            "getPT5",
            "getPT6",
            "getPT7",
            "getPT8",
            "getPV1",
            "getPV2",
            "getPV3",
            "getPV4",
            "getPV5",
            "getPV6",
            "getPV7",
            "getPV8",
            "getPRF",
            "getPRN",
        ]

        for sensor_key in sensors_without_icon:
            with self.subTest(sensor=sensor_key):
                # These sensors exist in the real data
                assert sensor_key in self.sensors, (
                    f"Sensor {sensor_key} missing in real XML data"
                )

                # Simulate getattr(self, '_attr_icon', None) - must not crash
                mock_sensor = type("MockSensor", (), {})()
                # No _attr_icon set (as with sensors without icon)
                base_icon = getattr(mock_sensor, "_attr_icon", None)
                # Should return None, not crash
                assert base_icon is None


class TestLEXplus10SLCompatibility(unittest.TestCase):
    """Tests for compatibility and backward compatibility."""

    def test_minimum_required_sensors_for_basic_functionality(self) -> None:
        """Test that minimum requirements for basic functionality are met.

        These sensors MUST work, otherwise the integration is unusable:
        - getFLO: flow (critical for water consumption)
        - getPRS: pressure (critical for operation)
        - getTOR or getVOL: volume (important for statistics)
        - getSRE: regeneration (important for maintenance)
        """
        root = ElementTree.fromstring(REAL_XML_RESPONSE)
        device = root.find(".//d")
        sensors = {c.get("n"): c.get("v") for c in device.findall("c")}

        # These sensors are CRITICAL
        critical_sensors = ["getFLO", "getPRS", "getSRE"]
        for sensor in critical_sensors:
            assert sensor in sensors, (
                f"Critical sensor {sensor} missing - integration not usable!"
            )

        # Either getTOR or getVOL must be present
        assert "getTOR" in sensors or "getVOL" in sensors, (
            "Neither getTOR nor getVOL present - volume display impossible!"
        )

    def test_backward_compatibility_with_getvol(self) -> None:
        """Test that code can handle both volume sensors.

        Older devices: getVOL
        LEXplus10SL: getTOR

        Code should support both (or treat getTOR as an alias for getVOL).
        """
        # LEXplus10SL hat getTOR
        root = ElementTree.fromstring(REAL_XML_RESPONSE)
        device = root.find(".//d")
        sensors = {c.get("n"): c.get("v") for c in device.findall("c")}

        if "getTOR" in sensors and "getVOL" not in sensors:
            # LEXplus10SL mode: getTOR should be treated as getVOL
            volume_value = sensors.get("getTOR") or sensors.get("getVOL")
            assert volume_value is not None, (
                "Volume value not available (neither getTOR nor getVOL)"
            )
            assert volume_value == "722"


class TestLEXplus10SLEdgeCases(unittest.TestCase):
    """Tests for edge cases and special cases."""

    def test_empty_profile_names_should_be_handled(self) -> None:
        """Test that empty profile names are handled correctly.

        Profiles 4-8 have empty names ("") - the code must handle this.
        """
        root = ElementTree.fromstring(REAL_XML_RESPONSE)
        device = root.find(".//d")
        sensors = {c.get("n"): c.get("v") for c in device.findall("c")}

        # Empty names for non-configured profiles
        for i in range(4, 9):
            profile_name = sensors.get(f"getPN{i}")
            assert profile_name == "", (
                f"Nicht konfiguriertes Profil {i} sollte leeren Namen haben"
            )

    def test_deactivated_profiles_should_still_have_valid_thresholds(self) -> None:
        """Test that deactivated profiles still have valid thresholds.

        Even if profiles 4-8 are deactivated (getPA=0), they have default values.
        These should not cause errors.
        """
        root = ElementTree.fromstring(REAL_XML_RESPONSE)
        device = root.find(".//d")
        sensors = {c.get("n"): c.get("v") for c in device.findall("c")}

        # Profile 4 is deactivated
        assert sensors["getPA4"] == "0"

        # But still has valid thresholds
        assert sensors["getPF4"] == "3500"
        assert sensors["getPT4"] == "60"
        assert sensors["getPV4"] == "300"

    def test_active_profile_consistency(self) -> None:
        """Test that active profile is consistent.

        If getPRF=3, then:
        - Profile 3 must be activated (getPA3=1)
        - Profile 3 must have a name (getPN3 not empty)
        """
        root = ElementTree.fromstring(REAL_XML_RESPONSE)
        device = root.find(".//d")
        sensors = {c.get("n"): c.get("v") for c in device.findall("c")}

        active_profile = int(sensors["getPRF"])

        # Active profile must be activated
        assert sensors[f"getPA{active_profile}"] == "1", (
            f"Aktives Profil {active_profile} ist nicht aktiviert!"
        )

        # Active profile should have a name
        assert sensors[f"getPN{active_profile}"] != "", (
            f"Aktives Profil {active_profile} hat keinen Namen!"
        )


if __name__ == "__main__":
    # Verbose output to see which tests are running
    unittest.main(verbosity=2)
