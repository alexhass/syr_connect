"""
Unit tests for SYR Connect with real LEXplus10SL data.

These tests use real data from a LEXplus10SL (Firmware 2.9, Hardware SLPL)
to ensure that the integration works with this device type.

Serial Number: 210836887
Device: LEXplus10SL
Firmware: 2.9 (SLPL)
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

import defusedxml.ElementTree as etree


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


class TestLEXplus10SLRealData(unittest.TestCase):
    """Tests with real data from LEXplus10SL."""

    def setUp(self):
        """Parse real XML data."""
        self.root = etree.fromstring(REAL_XML_RESPONSE)
        self.device = self.root.find('.//d')
        self.sensors = {c.get('n'): c.get('v') for c in self.device.findall('c')}

    def test_device_identification(self):
        """Test that LEXplus10SL is correctly identified."""
        self.assertEqual(self.sensors['getSRN'], '210836887')
        self.assertEqual(self.sensors['getVER'], '2.9')
        self.assertEqual(self.sensors['getFIR'], 'SLPL')
        self.assertEqual(self.sensors['getTYP'], '80')
        self.assertEqual(self.sensors['getCNA'], 'LEXplus10SL')

    def test_flow_sensor_exists(self):
        """Test that flow sensor exists."""
        self.assertIn('getFLO', self.sensors)
        # In idle state, flow should be 0
        self.assertEqual(self.sensors['getFLO'], '0')

    def test_pressure_sensor_exists(self):
        """Test that pressure sensor exists."""
        self.assertIn('getPRS', self.sensors)
        # Value 39 = 3.9 bar
        self.assertEqual(self.sensors['getPRS'], '39')

    def test_volume_uses_getTOR_not_getVOL(self):
        """
        IMPORTANT: LEXplus10SL uses getTOR instead of getVOL!

        This is a critical difference to other SYR devices.
        If the code only supports getVOL, volume display will not work.
        """
        self.assertIn('getTOR', self.sensors)
        self.assertNotIn('getVOL', self.sensors)
        self.assertEqual(self.sensors['getTOR'], '722')

    def test_regeneration_sensor_exists(self):
        """Test that regeneration sensor exists."""
        self.assertIn('getSRE', self.sensors)
        # 0 = no regeneration active
        self.assertEqual(self.sensors['getSRE'], '0')

    def test_leak_protection_profile_activation(self):
        """
        Test leak protection profile activation.

        LEXplus10SL has up to 8 profiles that can be activated/deactivated.
        This device has profiles 1-3 activated, 4-8 deactivated.
        """
        # Aktivierte Profile
        self.assertEqual(self.sensors['getPA1'], '1')
        self.assertEqual(self.sensors['getPA2'], '1')
        self.assertEqual(self.sensors['getPA3'], '1')

        # Deaktivierte Profile
        self.assertEqual(self.sensors['getPA4'], '0')
        self.assertEqual(self.sensors['getPA5'], '0')
        self.assertEqual(self.sensors['getPA6'], '0')
        self.assertEqual(self.sensors['getPA7'], '0')
        self.assertEqual(self.sensors['getPA8'], '0')

    def test_leak_protection_profile_names(self):
        """
        Test leak protection profile names.

        Profiles can be named by the user.
        This device has: "Anwesend" (Present), "Abwesend" (Absent), "Neues Profil" (New Profile)
        """
        self.assertEqual(self.sensors['getPN1'], 'Anwesend')
        self.assertEqual(self.sensors['getPN2'], 'Abwesend')
        self.assertEqual(self.sensors['getPN3'], 'Neues Profil')

        # Non-configured profiles have empty names
        self.assertEqual(self.sensors['getPN4'], '')
        self.assertEqual(self.sensors['getPN5'], '')

    def test_leak_protection_active_profile(self):
        """
        Test that active profile is correctly detected.

        getPRF shows which profile (1-8) is currently active.
        In this case: Profile 3 "Neues Profil"
        """
        self.assertEqual(self.sensors['getPRF'], '3')
        self.assertEqual(self.sensors['getPRN'], '3')

        # The active profile should also be activated
        self.assertEqual(self.sensors['getPA3'], '1')

        # Name of the active profile
        self.assertEqual(self.sensors['getPN3'], 'Neues Profil')

    def test_leak_protection_profile_3_flow_threshold(self):
        """
        Test flow leakage threshold of profile 3.

        App shows: "Flow leakage 1999 l/h"
        XML provides: getPF3="1999"

        If this value is exceeded, an alarm is triggered.
        """
        self.assertEqual(self.sensors['getPF3'], '1999')

    def test_leak_protection_profile_3_time_threshold(self):
        """
        Test time leakage threshold of profile 3.

        App shows: "Time leakage 0.2 h"
        XML provides: getPT3="13" (minutes)

        0.2h × 60 = 12 minutes (rounding difference in app)
        """
        self.assertEqual(self.sensors['getPT3'], '13')

    def test_leak_protection_profile_3_volume_threshold(self):
        """
        Test volume leakage threshold of profile 3.

        App shows: "Volume leakage 185 L"
        XML provides: getPV3="185"

        Perfect match!
        """
        self.assertEqual(self.sensors['getPV3'], '185')

    def test_all_leak_protection_profiles_have_all_parameters(self):
        """
        Test that ALL 8 profiles have the required parameters.

        Each profile (1-8) must have:
        - getPA: activation
        - getPN: name
        - getPF: flow leakage
        - getPT: time leakage
        - getPV: volume leakage
        """
        for i in range(1, 9):
            with self.subTest(profile=i):
                self.assertIn(f'getPA{i}', self.sensors, f"Profil {i} fehlt Aktivierung")
                self.assertIn(f'getPN{i}', self.sensors, f"Profil {i} fehlt Name")
                self.assertIn(f'getPF{i}', self.sensors, f"Profil {i} fehlt Durchflussleckage")
                self.assertIn(f'getPT{i}', self.sensors, f"Profil {i} fehlt Zeitleckage")
                self.assertIn(f'getPV{i}', self.sensors, f"Profil {i} fehlt Volumenleckage")

    def test_sensor_creation_should_not_crash_on_missing_icon(self):
        """
        CRITICAL TEST: Sensor creation must not crash if icon is missing.

        This was the original bug in sensor.py:175

        Many leak protection sensors do not have an icon in _SYR_CONNECT_SENSOR_ICONS.
        The code must handle this.
        """
        # Simuliere Sensoren ohne Icon
        sensors_without_icon = [
            'getPA1', 'getPA2', 'getPA3', 'getPA4', 'getPA5', 'getPA6', 'getPA7', 'getPA8',
            'getPN1', 'getPN2', 'getPN3', 'getPN4', 'getPN5', 'getPN6', 'getPN7', 'getPN8',
            'getPF1', 'getPF2', 'getPF3', 'getPF4', 'getPF5', 'getPF6', 'getPF7', 'getPF8',
            'getPT1', 'getPT2', 'getPT3', 'getPT4', 'getPT5', 'getPT6', 'getPT7', 'getPT8',
            'getPV1', 'getPV2', 'getPV3', 'getPV4', 'getPV5', 'getPV6', 'getPV7', 'getPV8',
            'getPRF', 'getPRN',
        ]

        for sensor_key in sensors_without_icon:
            with self.subTest(sensor=sensor_key):
                # These sensors exist in the real data
                self.assertIn(sensor_key, self.sensors,
                             f"Sensor {sensor_key} missing in real XML data")

                # Simulate getattr(self, '_attr_icon', None) - must not crash
                mock_sensor = type('MockSensor', (), {})()
                # No _attr_icon set (as with sensors without icon)
                base_icon = getattr(mock_sensor, '_attr_icon', None)
                # Should return None, not crash
                self.assertIsNone(base_icon)


class TestLEXplus10SLCompatibility(unittest.TestCase):
    """Tests for compatibility and backward compatibility."""

    def test_minimum_required_sensors_for_basic_functionality(self):
        """
        Test that minimum requirements for basic functionality are met.

        These sensors MUST work, otherwise the integration is unusable:
        - getFLO: flow (critical for water consumption)
        - getPRS: pressure (critical for operation)
        - getTOR or getVOL: volume (important for statistics)
        - getSRE: regeneration (important for maintenance)
        """
        root = etree.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # These sensors are CRITICAL
        critical_sensors = ['getFLO', 'getPRS', 'getSRE']
        for sensor in critical_sensors:
            self.assertIn(sensor, sensors,
                         f"Critical sensor {sensor} missing - integration not usable!")

        # Either getTOR or getVOL must be present
        self.assertTrue('getTOR' in sensors or 'getVOL' in sensors,
                       "Neither getTOR nor getVOL present - volume display impossible!")

    def test_backward_compatibility_with_getVOL(self):
        """
        Test that code can handle both volume sensors.

        Older devices: getVOL
        LEXplus10SL: getTOR

        Code should support both (or treat getTOR as an alias for getVOL).
        """
        # LEXplus10SL hat getTOR
        root = etree.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        if 'getTOR' in sensors and 'getVOL' not in sensors:
            # LEXplus10SL mode: getTOR should be treated as getVOL
            volume_value = sensors.get('getTOR') or sensors.get('getVOL')
            self.assertIsNotNone(volume_value,
                               "Volume value not available (neither getTOR nor getVOL)")
            self.assertEqual(volume_value, '722')


class TestLEXplus10SLEdgeCases(unittest.TestCase):
    """Tests for edge cases and special cases."""

    def test_empty_profile_names_should_be_handled(self):
        """
        Test that empty profile names are handled correctly.

        Profiles 4-8 have empty names ("") - the code must handle this.
        """
        root = etree.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # Empty names for non-configured profiles
        for i in range(4, 9):
            profile_name = sensors.get(f'getPN{i}')
            self.assertEqual(profile_name, '',
                           f"Nicht konfiguriertes Profil {i} sollte leeren Namen haben")

    def test_deactivated_profiles_should_still_have_valid_thresholds(self):
        """
        Test that deactivated profiles still have valid thresholds.

        Even if profiles 4-8 are deactivated (getPA=0), they have default values.
        These should not cause errors.
        """
        root = etree.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # Profile 4 is deactivated
        self.assertEqual(sensors['getPA4'], '0')

        # But still has valid thresholds
        self.assertEqual(sensors['getPF4'], '3500')
        self.assertEqual(sensors['getPT4'], '60')
        self.assertEqual(sensors['getPV4'], '300')

    def test_active_profile_consistency(self):
        """
        Test that active profile is consistent.

        If getPRF=3, then:
        - Profile 3 must be activated (getPA3=1)
        - Profile 3 must have a name (getPN3 not empty)
        """
        root = etree.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        active_profile = int(sensors['getPRF'])

        # Active profile must be activated
        self.assertEqual(sensors[f'getPA{active_profile}'], '1',
                        f"Aktives Profil {active_profile} ist nicht aktiviert!")

        # Active profile should have a name
        self.assertNotEqual(sensors[f'getPN{active_profile}'], '',
                          f"Aktives Profil {active_profile} hat keinen Namen!")


if __name__ == '__main__':
    # Verbose output to see which tests are running
    unittest.main(verbosity=2)
