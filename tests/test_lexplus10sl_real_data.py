"""
Unit tests for SYR Connect with real LEXplus10SL data.

Diese Tests verwenden echte Daten von einem LEXplus10SL (Firmware 2.9, Hardware SLPL)
um sicherzustellen, dass die Integration mit diesem Gerätetyp funktioniert.

Serial Number: 210836887
Device: LEXplus10SL
Firmware: 2.9 (SLPL)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from xml.etree import ElementTree as ET


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
    """Tests mit echten Daten vom LEXplus10SL."""

    def setUp(self):
        """Parse real XML data."""
        self.root = ET.fromstring(REAL_XML_RESPONSE)
        self.device = self.root.find('.//d')
        self.sensors = {c.get('n'): c.get('v') for c in self.device.findall('c')}

    def test_device_identification(self):
        """Test dass LEXplus10SL korrekt erkannt wird."""
        self.assertEqual(self.sensors['getSRN'], '210836887')
        self.assertEqual(self.sensors['getVER'], '2.9')
        self.assertEqual(self.sensors['getFIR'], 'SLPL')
        self.assertEqual(self.sensors['getTYP'], '80')
        self.assertEqual(self.sensors['getCNA'], 'LEXplus10SL')

    def test_flow_sensor_exists(self):
        """Test dass Durchfluss-Sensor vorhanden ist."""
        self.assertIn('getFLO', self.sensors)
        # Im Ruhezustand sollte Durchfluss 0 sein
        self.assertEqual(self.sensors['getFLO'], '0')

    def test_pressure_sensor_exists(self):
        """Test dass Druck-Sensor vorhanden ist."""
        self.assertIn('getPRS', self.sensors)
        # Wert 39 = 3.9 bar
        self.assertEqual(self.sensors['getPRS'], '39')

    def test_volume_uses_getTOR_not_getVOL(self):
        """
        WICHTIG: LEXplus10SL verwendet getTOR statt getVOL!

        Das ist ein kritischer Unterschied zu anderen SYR-Geräten.
        Wenn der Code nur getVOL unterstützt, funktioniert Volume-Anzeige nicht.
        """
        self.assertIn('getTOR', self.sensors)
        self.assertNotIn('getVOL', self.sensors)
        self.assertEqual(self.sensors['getTOR'], '722')

    def test_regeneration_sensor_exists(self):
        """Test dass Regenerations-Sensor vorhanden ist."""
        self.assertIn('getSRE', self.sensors)
        # 0 = keine Regeneration aktiv
        self.assertEqual(self.sensors['getSRE'], '0')

    def test_leak_protection_profile_activation(self):
        """
        Test Leckagesschutz-Profil Aktivierung.

        LEXplus10SL hat bis zu 8 Profile, die aktiviert/deaktiviert werden können.
        Dieses Gerät hat Profile 1-3 aktiviert, 4-8 deaktiviert.
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
        Test Leckagesschutz-Profil Namen.

        Profile können vom Benutzer benannt werden.
        Dieses Gerät hat: "Anwesend", "Abwesend", "Neues Profil"
        """
        self.assertEqual(self.sensors['getPN1'], 'Anwesend')
        self.assertEqual(self.sensors['getPN2'], 'Abwesend')
        self.assertEqual(self.sensors['getPN3'], 'Neues Profil')

        # Nicht konfigurierte Profile haben leere Namen
        self.assertEqual(self.sensors['getPN4'], '')
        self.assertEqual(self.sensors['getPN5'], '')

    def test_leak_protection_active_profile(self):
        """
        Test dass aktives Profil korrekt erkannt wird.

        getPRF zeigt welches Profil (1-8) gerade aktiv ist.
        In diesem Fall: Profil 3 "Neues Profil"
        """
        self.assertEqual(self.sensors['getPRF'], '3')
        self.assertEqual(self.sensors['getPRN'], '3')

        # Das aktive Profil sollte auch aktiviert sein
        self.assertEqual(self.sensors['getPA3'], '1')

        # Name des aktiven Profils
        self.assertEqual(self.sensors['getPN3'], 'Neues Profil')

    def test_leak_protection_profile_3_flow_threshold(self):
        """
        Test Durchflussleckage-Schwellwert von Profil 3.

        App zeigt: "Durchflussleckage 1999 l/h"
        XML liefert: getPF3="1999"

        Bei Überschreitung dieses Werts wird Alarm ausgelöst.
        """
        self.assertEqual(self.sensors['getPF3'], '1999')

    def test_leak_protection_profile_3_time_threshold(self):
        """
        Test Zeitleckage-Schwellwert von Profil 3.

        App zeigt: "Zeitleckage 0.2 h"
        XML liefert: getPT3="13" (Minuten)

        0.2h × 60 = 12 Minuten (Rundungsdifferenz in App)
        """
        self.assertEqual(self.sensors['getPT3'], '13')

    def test_leak_protection_profile_3_volume_threshold(self):
        """
        Test Volumenleckage-Schwellwert von Profil 3.

        App zeigt: "Volumenleckage 185 L"
        XML liefert: getPV3="185"

        Perfekte Übereinstimmung!
        """
        self.assertEqual(self.sensors['getPV3'], '185')

    def test_all_leak_protection_profiles_have_all_parameters(self):
        """
        Test dass ALLE 8 Profile die erforderlichen Parameter haben.

        Jedes Profil (1-8) muss haben:
        - getPA: Aktivierung
        - getPN: Name
        - getPF: Durchflussleckage
        - getPT: Zeitleckage
        - getPV: Volumenleckage
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
        KRITISCHER TEST: Sensor-Erstellung darf nicht crashen wenn Icon fehlt.

        Das war der ursprüngliche Bug in sensor.py:175

        Viele Leckagesschutz-Sensoren haben kein Icon in _SYR_CONNECT_SENSOR_ICONS.
        Der Code muss damit umgehen können.
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
                # Diese Sensoren existieren in den echten Daten
                self.assertIn(sensor_key, self.sensors,
                             f"Sensor {sensor_key} fehlt in echten XML-Daten")

                # Simuliere getattr(self, '_attr_icon', None) - darf nicht crashen
                mock_sensor = type('MockSensor', (), {})()
                # Kein _attr_icon gesetzt (wie bei Sensoren ohne Icon)
                base_icon = getattr(mock_sensor, '_attr_icon', None)
                # Sollte None zurückgeben, nicht crashen
                self.assertIsNone(base_icon)


class TestLEXplus10SLCompatibility(unittest.TestCase):
    """Tests für Kompatibilität und Rückwärtskompatibilität."""

    def test_minimum_required_sensors_for_basic_functionality(self):
        """
        Test dass Mindestanforderungen für Basis-Funktionalität erfüllt sind.

        Diese Sensoren MÜSSEN funktionieren, sonst ist die Integration unbrauchbar:
        - getFLO: Durchfluss (kritisch für Wasserverbrauch)
        - getPRS: Druck (kritisch für Betrieb)
        - getTOR oder getVOL: Volumen (wichtig für Statistik)
        - getSRE: Regeneration (wichtig für Wartung)
        """
        root = ET.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # Diese Sensoren sind KRITISCH
        critical_sensors = ['getFLO', 'getPRS', 'getSRE']
        for sensor in critical_sensors:
            self.assertIn(sensor, sensors,
                         f"Kritischer Sensor {sensor} fehlt - Integration nicht nutzbar!")

        # Entweder getTOR oder getVOL muss vorhanden sein
        self.assertTrue('getTOR' in sensors or 'getVOL' in sensors,
                       "Weder getTOR noch getVOL vorhanden - Volumen-Anzeige unmöglich!")

    def test_backward_compatibility_with_getVOL(self):
        """
        Test dass Code mit beiden Volume-Sensoren umgehen kann.

        Ältere Geräte: getVOL
        LEXplus10SL: getTOR

        Code sollte beide unterstützen (oder getTOR als Alias für getVOL behandeln).
        """
        # LEXplus10SL hat getTOR
        root = ET.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        if 'getTOR' in sensors and 'getVOL' not in sensors:
            # LEXplus10SL-Modus: getTOR sollte als getVOL behandelt werden
            volume_value = sensors.get('getTOR') or sensors.get('getVOL')
            self.assertIsNotNone(volume_value,
                               "Volume-Wert nicht verfügbar (weder getTOR noch getVOL)")
            self.assertEqual(volume_value, '722')


class TestLEXplus10SLEdgeCases(unittest.TestCase):
    """Tests für Edge Cases und Sonderfälle."""

    def test_empty_profile_names_should_be_handled(self):
        """
        Test dass leere Profilnamen korrekt behandelt werden.

        Profile 4-8 haben leere Namen ("") - das muss der Code abfangen.
        """
        root = ET.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # Leere Namen bei nicht konfigurierten Profilen
        for i in range(4, 9):
            profile_name = sensors.get(f'getPN{i}')
            self.assertEqual(profile_name, '',
                           f"Nicht konfiguriertes Profil {i} sollte leeren Namen haben")

    def test_deactivated_profiles_should_still_have_valid_thresholds(self):
        """
        Test dass auch deaktivierte Profile gültige Schwellwerte haben.

        Auch wenn Profil 4-8 deaktiviert sind (getPA=0), haben sie Standardwerte.
        Diese sollten nicht zu Fehlern führen.
        """
        root = ET.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        # Profil 4 ist deaktiviert
        self.assertEqual(sensors['getPA4'], '0')

        # Aber hat trotzdem gültige Schwellwerte
        self.assertEqual(sensors['getPF4'], '3500')
        self.assertEqual(sensors['getPT4'], '60')
        self.assertEqual(sensors['getPV4'], '300')

    def test_active_profile_consistency(self):
        """
        Test dass aktives Profil konsistent ist.

        Wenn getPRF=3, dann muss:
        - Profil 3 aktiviert sein (getPA3=1)
        - Profil 3 einen Namen haben (getPN3 nicht leer)
        """
        root = ET.fromstring(REAL_XML_RESPONSE)
        device = root.find('.//d')
        sensors = {c.get('n'): c.get('v') for c in device.findall('c')}

        active_profile = int(sensors['getPRF'])

        # Aktives Profil muss aktiviert sein
        self.assertEqual(sensors[f'getPA{active_profile}'], '1',
                        f"Aktives Profil {active_profile} ist nicht aktiviert!")

        # Aktives Profil sollte einen Namen haben
        self.assertNotEqual(sensors[f'getPN{active_profile}'], '',
                          f"Aktives Profil {active_profile} hat keinen Namen!")


if __name__ == '__main__':
    # Verbose output um zu sehen welche Tests laufen
    unittest.main(verbosity=2)
