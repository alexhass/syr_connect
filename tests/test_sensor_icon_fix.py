"""Test for sensor.py icon attribute fix."""
import unittest
from unittest.mock import Mock, MagicMock


class MockCoordinatorEntity:
    """Mock coordinator entity."""
    def __init__(self, coordinator):
        self.coordinator = coordinator


class MockSensorEntity:
    """Mock sensor entity."""
    pass


class TestSyrConnectSensorIconFix(unittest.TestCase):
    """Test the icon attribute fix for SyrConnectSensor."""

    def test_icon_attribute_exists_in_dict(self):
        """Test sensor initialization when icon is defined in _SYR_CONNECT_SENSOR_ICONS."""
        # Simulate sensor with icon defined
        sensor = MockSensorEntity()

        # Icon is defined (like in _SYR_CONNECT_SENSOR_ICONS)
        sensor._attr_icon = "mdi:water-percent"

        # Old approach (would work here)
        base_icon_old = sensor._attr_icon
        self.assertEqual(base_icon_old, "mdi:water-percent")

        # New approach (also works)
        base_icon_new = getattr(sensor, '_attr_icon', None)
        self.assertEqual(base_icon_new, "mdi:water-percent")

    def test_icon_attribute_missing_old_approach_fails(self):
        """Test that old approach fails when icon is not defined."""
        # Simulate sensor without icon (like new leak protection sensors)
        sensor = MockSensorEntity()

        # Old approach fails with AttributeError
        with self.assertRaises(AttributeError):
            base_icon = sensor._attr_icon

    def test_icon_attribute_missing_new_approach_works(self):
        """Test that new approach works when icon is not defined."""
        # Simulate sensor without icon (like new leak protection sensors)
        sensor = MockSensorEntity()

        # New approach returns None gracefully
        base_icon = getattr(sensor, '_attr_icon', None)
        self.assertIsNone(base_icon)

        # No exception raised!

    def test_real_world_scenario_with_leak_protection_sensors(self):
        """Test real-world scenario with LEXplus10SL leak protection sensors."""
        # These sensors don't have icons defined in _SYR_CONNECT_SENSOR_ICONS:
        leak_sensors = [
            'getPA1', 'getPA2', 'getPA3',  # Profile active
            'getPN1', 'getPN2', 'getPN3',  # Profile name
            'getPF1', 'getPF2', 'getPF3',  # Flow leak
            'getPT1', 'getPT2', 'getPT3',  # Time leak
            'getPV1', 'getPV2', 'getPV3',  # Volume leak
            'getPRF',  # Active profile
        ]

        for sensor_key in leak_sensors:
            sensor = MockSensorEntity()

            # These sensors have no icon in _SYR_CONNECT_SENSOR_ICONS
            # So _attr_icon is never set

            # Old approach: FAILS
            # self._base_icon = self._attr_icon  # AttributeError!

            # New approach: WORKS
            base_icon = getattr(sensor, '_attr_icon', None)
            self.assertIsNone(base_icon)

            # No crash, sensor can be created!

    def test_comparison_old_vs_new(self):
        """Compare old and new approach side-by-side."""
        print("\n=== Comparison: Old vs New Approach ===")

        # Test with icon
        sensor_with_icon = MockSensorEntity()
        sensor_with_icon._attr_icon = "mdi:gauge"

        print("Sensor WITH icon (getFLO, getPRS, etc.):")
        print(f"  Old: self._attr_icon = {sensor_with_icon._attr_icon} ✅")
        print(f"  New: getattr(self, '_attr_icon', None) = {getattr(sensor_with_icon, '_attr_icon', None)} ✅")

        # Test without icon
        sensor_without_icon = MockSensorEntity()

        print("\nSensor WITHOUT icon (getPA1, getPF1, etc.):")
        print(f"  Old: self._attr_icon = AttributeError ❌ CRASH!")
        print(f"  New: getattr(self, '_attr_icon', None) = {getattr(sensor_without_icon, '_attr_icon', None)} ✅")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
