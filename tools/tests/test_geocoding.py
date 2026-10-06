import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition.geocoding import (address_equivalence_key, address_hash,
                                   addresses_equivalent_after_standardization,
                                   geocode_batch, geocode_candidates,
                                   google_maps_search_url, group_candidates,
                                   normalize_address, standardize_taiwan_address,
                                   stored_rows, validate_result)


class GeocodingTests(unittest.TestCase):
    def test_normalized_addresses_dedupe_and_hash_consistently(self):
        self.assertEqual(normalize_address("臺北市 信義區松仁路 100 號"),
                         normalize_address("台北市信義區松仁路100號"))
        self.assertEqual(address_hash("臺北市 松仁路100號"), address_hash("台北市松仁路100號"))

    def test_group_candidates_preserves_area_variants_but_dedupes_request(self):
        grouped = group_candidates([("a1", "臺北市 松仁路100號"), ("a2", "台北市松仁路100號"),
                                    ("a3", "   ")])
        self.assertEqual(len(grouped), 1)
        self.assertEqual({row["area_key"] for row in grouped[0]["areas"]}, {"a1", "a2"})

    def test_taiwan_standardization_uses_official_city_and_numeric_address_parts(self):
        self.assertEqual(standardize_taiwan_address("台中市 西屯區工業區六路七號"),
                         "臺中市西屯區工業區六路7號")
        self.assertEqual(standardize_taiwan_address("臺中市西屯區工業區六路柒號"),
                         "臺中市西屯區工業區六路7號")
        self.assertEqual(standardize_taiwan_address("臺中市西屯區工業區六路一千二百三號"),
                         "臺中市西屯區工業區六路1203號")
        self.assertEqual(standardize_taiwan_address("臺中市西屯區協和里012鄰工業區六路7號"),
                         "臺中市西屯區協和里12鄰工業區六路7號")
        self.assertEqual(normalize_address("臺北市大安區三民路"),
                         normalize_address("台北市大安區三民路"))

    def test_address_equivalence_ignores_optional_village_and_neighbor_only(self):
        self.assertEqual(
            address_equivalence_key("臺中市西屯區工業區六路七號"),
            address_equivalence_key("臺中市西屯區協和里012鄰工業區六路7號"))
        self.assertTrue(addresses_equivalent_after_standardization(
            "臺中市西屯區工業區六路七號", "臺中市西屯區協和里012鄰工業區六路7號"))
        self.assertFalse(addresses_equivalent_after_standardization(
            "臺中市西屯區協和里工業區六路7號", "臺中市西屯區福安里工業區六路7號"))
        self.assertNotEqual(address_equivalence_key("臺中市西屯區工業區六路7號"),
                            address_equivalence_key("臺中市西屯區工業區六路8號"))

    def test_area_description_completes_a_relative_street_address(self):
        candidate = group_candidates([("a1", "台中市西屯區", "工業區六路七號")])[0]
        self.assertEqual(candidate["canonical_address"], "臺中市西屯區工業區六路7號")
        self.assertEqual(candidate["geocoder_query"], "工業區六路7號")
        self.assertEqual(candidate["areas"][0]["input_address"], "臺中市西屯區工業區六路7號")
        full_address = group_candidates([("a2", "臺中市西屯區協和里012鄰工業區六路七號")])[0]
        self.assertEqual(full_address["geocoder_query"], "工業區六路7號")

    def test_local_address_variant_is_upgraded_only_when_taiwan_keys_match(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"results": [{
                    "address": "臺中市西屯區協和里012鄰工業區六路7號",
                    "lon": 120.6, "lat": 24.17, "matchLevel": "ADDRESS_VARIANT",
                }]}).encode("utf-8")

        candidate = group_candidates([("a1", "台中市西屯區", "工業區六路七號")])
        result = geocode_candidates("http://localhost:3301", candidate,
                                    lambda *_args, **_kwargs: Response())[0]
        self.assertEqual(result["match_level"], "ADDRESS_STANDARDIZED")

    def test_google_maps_link_is_only_created_for_complete_taiwan_addresses(self):
        self.assertIsNotNone(google_maps_search_url("臺中市西屯區工業區六路7號"))
        self.assertIsNone(google_maps_search_url("公司指定派遣的辦公室"))
        self.assertIsNone(google_maps_search_url("xxx路xxx號"))

    def test_not_found_is_a_valid_non_coordinate_result(self):
        self.assertEqual(validate_result(None)["match_level"], "NOT_FOUND")

    def test_result_quality_and_wgs84_coordinates_are_validated(self):
        result = validate_result({"address": "台北市松仁路100號", "lon": "121.5", "lat": "25",
                                  "strategy": "address", "matchLevel": "EXACT_TEXT"})
        self.assertEqual(result["latitude"], 25)
        with self.assertRaisesRegex(ValueError, "matchLevel"):
            validate_result({"address": "x", "lon": 121, "lat": 25, "matchLevel": "UNKNOWN"})
        with self.assertRaisesRegex(ValueError, "coordinates"):
            validate_result({"address": "x", "lon": 181, "lat": 25, "matchLevel": "EXACT_TEXT"})

    def test_batch_response_count_is_checked(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"results": []}).encode("utf-8")

        with self.assertRaisesRegex(ValueError, "count"):
            geocode_batch("http://localhost:3001", ["台北市"], lambda *_args, **_kwargs: Response())

    def test_stored_rows_fan_one_lookup_out_to_each_area_variant(self):
        candidates = group_candidates([("a1", "台北市松仁路100號"), ("a2", "臺北市 松仁路100號")])
        result = validate_result({"address": "台北市松仁路100號", "lon": 121.5, "lat": 25,
                                  "matchLevel": "EXACT_TEXT"})
        rows = stored_rows(candidates, [result])
        self.assertEqual({row[0] for row in rows}, {"a1", "a2"})
        self.assertEqual(rows[0][1], rows[1][1])
        self.assertEqual(rows[0][9], "臺北市松仁路100號")
        self.assertEqual(rows[0][10], "TW-ADDRESS-1")


if __name__ == "__main__":
    unittest.main()
