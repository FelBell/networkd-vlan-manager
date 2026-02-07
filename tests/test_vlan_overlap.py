import unittest
import os
import shutil
from vlan_manager.core import VlanManager
from vlan_manager.config import Config

class TestVlanOverlap(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_overlap_data'
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        self.original_data_file = Config.DATA_FILE
        Config.DATA_FILE = os.path.join(self.test_dir, 'vlans.json')

        self.manager = VlanManager()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config.DATA_FILE = self.original_data_file

    def test_add_overlapping_vlan(self):
        vlan1 = {
            "id": 10,
            "cidr": "192.168.10.1/24",
            "dhcp": False,
            "nat": True
        }
        self.manager.add_vlan(vlan1)

        # Exact same network
        vlan2 = {
            "id": 11,
            "cidr": "192.168.10.1/24",
            "dhcp": False,
            "nat": True
        }
        with self.assertRaises(ValueError) as cm:
            self.manager.add_vlan(vlan2)
        self.assertIn("overlaps", str(cm.exception))

        # Overlapping network (subnet)
        vlan3 = {
            "id": 12,
            "cidr": "192.168.10.0/25",
            "dhcp": False,
            "nat": True
        }
        with self.assertRaises(ValueError) as cm:
            self.manager.add_vlan(vlan3)
        self.assertIn("overlaps", str(cm.exception))

        # Overlapping network (superset)
        vlan4 = {
            "id": 13,
            "cidr": "192.168.0.0/16",
            "dhcp": False,
            "nat": True
        }
        with self.assertRaises(ValueError) as cm:
            self.manager.add_vlan(vlan4)
        self.assertIn("overlaps", str(cm.exception))

        # Non-overlapping network
        vlan5 = {
            "id": 14,
            "cidr": "192.168.11.1/24",
            "dhcp": False,
            "nat": True
        }
        self.manager.add_vlan(vlan5) # Should not raise

if __name__ == '__main__':
    unittest.main()
