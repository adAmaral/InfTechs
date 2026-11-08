import unittest

from scripts.inftechs_lib import classify


class ClassifyProductTests(unittest.TestCase):
    def test_excludes_complete_laptop_even_when_it_lists_components(self):
        item = {
            "title": (
                "Gaming Laptop Intel Core i7 32GB RAM 1TB SSD "
                "NVIDIA GeForce RTX 4070"
            )
        }
        self.assertIsNone(classify(item))

    def test_does_not_call_charger_a_desktop_power_supply(self):
        item = {
            "title": "65W AC Adapter Charger Power Supply Cord for Laptop"
        }
        self.assertIsNone(classify(item))

    def test_classifies_laptop_replacement_fan_as_cooling(self):
        item = {
            "title": "Replacement CPU Cooling Fan for Laptop Compatible with HP"
        }
        self.assertEqual(classify(item), "cooling")

    def test_prefers_memory_over_motherboard_compatibility_text(self):
        item = {
            "title": "32GB DDR3 RAM Kit Compatible with Asus Motherboard"
        }
        self.assertEqual(classify(item), "ram")

    def test_classifies_graphics_board_before_memory_terms(self):
        item = {
            "title": "NVIDIA Quadro Graphics Board 512MB DDR3 PCI Express"
        }
        self.assertEqual(classify(item), "gpu")

    def test_excludes_phone_case_from_computer_case_family(self):
        item = {
            "title": "iPod Touch Protective PC Case Cover"
        }
        self.assertIsNone(classify(item))

    def test_classifies_atx_computer_case(self):
        item = {
            "title": "ATX Mid Tower PC Case with Tempered Glass"
        }
        self.assertEqual(classify(item), "case")

    def test_excludes_cpu_holder_mount(self):
        item = {
            "title": "CPU Holder Bracket Universal Computer Mount Under-Desk"
        }
        self.assertIsNone(classify(item))

    def test_classifies_case_fan_as_cooling_from_category(self):
        item = {
            "title": "ARGB Fan for Computer Case and Liquid Radiator",
            "categories": ["Computer Components", "Fans & Cooling", "Case Fans"],
        }
        self.assertEqual(classify(item), "cooling")

    def test_excludes_laptop_case_and_keyboard_cover(self):
        item = {
            "title": "Hard Shell Case and Keyboard Cover for MacBook Air",
            "categories": ["Laptop Accessories", "Hard Shell Cases"],
        }
        self.assertIsNone(classify(item))

    def test_classifies_gpu_water_block_as_cooling(self):
        item = {
            "title": "GPU Water Block RTX 3080/3090",
            "categories": ["Fans & Cooling", "Water Cooling Systems"],
        }
        self.assertEqual(classify(item), "cooling")

    def test_excludes_vehicle_heater_despite_cooling_category(self):
        item = {
            "title": "Portable Car Heater with Heating Cooling Fan Function",
            "categories": ["Vehicle Electronics", "Cooling Fans"],
        }
        self.assertIsNone(classify(item))

    def test_motherboard_category_overrides_memory_standard_in_title(self):
        item = {
            "title": "MSI ATX DDR3 2600 LGA 1150 Motherboard",
            "categories": ["Internal Components", "Motherboards"],
        }
        self.assertEqual(classify(item), "motherboard")

    def test_memory_kit_stays_ram_when_compatible_with_motherboard(self):
        item = {
            "title": "32GB DDR3 RAM Kit Compatible with Asus Motherboard",
        }
        self.assertEqual(classify(item), "ram")

    def test_case_category_overrides_included_power_supply(self):
        item = {
            "title": "Apevia Mid Tower with Side Window and 450W PSU",
            "categories": ["External Components", "Computer Cases"],
        }
        self.assertEqual(classify(item), "case")

    def test_sound_card_is_not_a_motherboard(self):
        item = {
            "title": "ASUS Soundcard for ASUS Motherboards",
            "categories": ["Internal Components", "Internal Sound Cards"],
        }
        self.assertIsNone(classify(item))


if __name__ == "__main__":
    unittest.main()
