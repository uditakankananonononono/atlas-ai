"""P235 concepts batch 23 (221-230, units and everyday exact math): red-first."""
from __future__ import annotations

import unittest
from fractions import Fraction


class Batch23Test(unittest.TestCase):
    def setUp(self):
        from app.modules.instinct_doc import p235_concepts_batch23 as m
        self.m = m

    def test_celsius_to_fahrenheit_exact(self):
        self.assertEqual(self.m.celsius_to_fahrenheit_exact(0), Fraction(32))
        self.assertEqual(self.m.celsius_to_fahrenheit_exact(100),
                         Fraction(212))
        self.assertEqual(self.m.celsius_to_fahrenheit_exact(-40),
                         Fraction(-40))
        self.assertEqual(self.m.celsius_to_fahrenheit_exact(
            Fraction(1, 3)), Fraction(163, 5))
        with self.assertRaises(ValueError):
            self.m.celsius_to_fahrenheit_exact(1_000_001)
        with self.assertRaises(ValueError):
            self.m.celsius_to_fahrenheit_exact(1.5)

    def test_fahrenheit_to_celsius_exact(self):
        self.assertEqual(self.m.fahrenheit_to_celsius_exact(32), Fraction(0))
        self.assertEqual(self.m.fahrenheit_to_celsius_exact(-40),
                         Fraction(-40))
        self.assertEqual(self.m.fahrenheit_to_celsius_exact(212),
                         Fraction(100))
        self.assertEqual(self.m.fahrenheit_to_celsius_exact(33),
                         Fraction(5, 9))

    def test_km_to_miles_exact(self):
        self.assertEqual(self.m.km_to_miles_exact(
            Fraction(1609344, 1000000)), Fraction(1))
        self.assertEqual(self.m.km_to_miles_exact(0), Fraction(0))
        self.assertEqual(self.m.km_to_miles_exact(1),
                         Fraction(15625, 25146))

    def test_miles_to_km_exact(self):
        self.assertEqual(self.m.miles_to_km_exact(1),
                         Fraction(1609344, 1000000))
        self.assertEqual(self.m.miles_to_km_exact(0), Fraction(0))
        self.assertEqual(self.m.miles_to_km_exact(10),
                         Fraction(1609344, 100000))

    def test_bmi_exact(self):
        self.assertEqual(self.m.bmi_exact(70, Fraction(7, 4)),
                         Fraction(160, 7))
        self.assertEqual(self.m.bmi_exact(50, 2), Fraction(25, 2))
        with self.assertRaises(ValueError):
            self.m.bmi_exact(70, 0)
        with self.assertRaises(ValueError):
            self.m.bmi_exact(0, 2)
        with self.assertRaises(ValueError):
            self.m.bmi_exact(1001, 2)

    def test_speed_mps_exact(self):
        self.assertEqual(self.m.speed_mps_exact(100, 9), Fraction(100, 9))
        self.assertEqual(self.m.speed_mps_exact(0, 5), Fraction(0))
        with self.assertRaises(ValueError):
            self.m.speed_mps_exact(100, 0)
        with self.assertRaises(ValueError):
            self.m.speed_mps_exact(-1, 5)
        with self.assertRaises(ValueError):
            self.m.speed_mps_exact(10**9 + 1, 1)

    def test_degrees_to_pi_fraction(self):
        self.assertEqual(self.m.degrees_to_pi_fraction(180), Fraction(1))
        self.assertEqual(self.m.degrees_to_pi_fraction(90), Fraction(1, 2))
        self.assertEqual(self.m.degrees_to_pi_fraction(360), Fraction(2))
        self.assertEqual(self.m.degrees_to_pi_fraction(-30),
                         Fraction(-1, 6))
        with self.assertRaises(ValueError):
            self.m.degrees_to_pi_fraction(1_000_001)

    def test_pi_fraction_to_degrees(self):
        self.assertEqual(self.m.pi_fraction_to_degrees(1, 2), Fraction(90))
        self.assertEqual(self.m.pi_fraction_to_degrees(2, 1), Fraction(360))
        self.assertEqual(self.m.pi_fraction_to_degrees(-1, 6),
                         Fraction(-30))
        with self.assertRaises(ValueError):
            self.m.pi_fraction_to_degrees(1, 0)

    def test_time_12h_to_24h(self):
        self.assertEqual(self.m.time_12h_to_24h("12:00 AM"), "00:00")
        self.assertEqual(self.m.time_12h_to_24h("12:00 PM"), "12:00")
        self.assertEqual(self.m.time_12h_to_24h("1:05 PM"), "13:05")
        self.assertEqual(self.m.time_12h_to_24h("11:59 AM"), "11:59")
        self.assertEqual(self.m.time_12h_to_24h("12:30 am"), "00:30")
        self.assertEqual(self.m.time_12h_to_24h("1:05 pm"), "13:05")
        for bad in ("13:00 PM", "1:60 PM", "1:00", "0:30 AM", "1:5 PM",
                    "1:05XM", "1:05pm", "1:05 Pm", "1:05 PM\n",
                    "1:05 PM ", " 1:05 PM"):
            with self.assertRaises(ValueError, msg=bad):
                self.m.time_12h_to_24h(bad)

    def test_time_24h_to_12h(self):
        self.assertEqual(self.m.time_24h_to_12h("00:00"), "12:00 AM")
        self.assertEqual(self.m.time_24h_to_12h("13:05"), "1:05 PM")
        self.assertEqual(self.m.time_24h_to_12h("12:00"), "12:00 PM")
        self.assertEqual(self.m.time_24h_to_12h("23:59"), "11:59 PM")
        for bad in ("24:00", "9:99", "9:00", "1:0", "ab:cd", "13:05\n",
                    "13:05 "):
            with self.assertRaises(ValueError, msg=bad):
                self.m.time_24h_to_12h(bad)


if __name__ == "__main__":
    unittest.main()
