import unittest
import os
import shutil
import json
from vlan_manager.core import VlanManager
from vlan_manager.config import Config

class TestDhcp(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_dhcp_data'
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        self.original_data_file = Config.DATA_FILE
        self.original_network_dir = Config.NETWORK_DIR
        self.original_kea_config = Config.KEA_CONFIG_FILE

        Config.DATA_FILE = os.path.join(self.test_dir, 'vlans.json')
        Config.NETWORK_DIR = os.path.join(self.test_dir, 'network')
        Config.KEA_CONFIG_FILE = os.path.join(self.test_dir, 'kea/kea-dhcp4.conf')

        os.makedirs(Config.NETWORK_DIR, exist_ok=True)
        self.manager = VlanManager()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        Config.DATA_FILE = self.original_data_file
        Config.NETWORK_DIR = self.original_network_dir
        Config.KEA_CONFIG_FILE = self.original_kea_config

    def test_dhcp_defaults(self):
        vlan = {
            "id": 10,
            "cidr": "192.168.10.1/24",
            "dhcp": True
        }
        self.manager.add_vlan(vlan)
        vlans = self.manager.get_vlans()
        added_vlan = vlans[0]

        self.assertEqual(added_vlan['dhcp_gateway'], "192.168.10.1")
        self.assertEqual(added_vlan['dhcp_dns'], "192.168.10.1")
        # 254 usable hosts. 80% of 254 is 203.
        # hosts are .1 to .254.
        # Last 203 hosts are hosts[-203:] -> hosts[254-203] to hosts[253]
        # hosts[51] to hosts[253]
        # hosts[0] is .1. hosts[51] is .52. hosts[253] is .254.
        self.assertEqual(added_vlan['dhcp_pools'], "192.168.10.52 - 192.168.10.254")

    def test_kea_config_generation(self):
        vlan = {
            "id": 20,
            "cidr": "10.0.0.1/24",
            "dhcp": True,
            "dhcp_gateway": "10.0.0.1",
            "dhcp_dns": "8.8.8.8",
            "dhcp_pools": "10.0.0.100 - 10.0.0.200"
        }
        self.manager.add_vlan(vlan)
        kea_config = self.manager.generate_kea_config()

        subnet = kea_config['Dhcp4']['subnet4'][0]
        self.assertEqual(subnet['subnet'], "10.0.0.0/24")
        self.assertEqual(subnet['pools'][0]['pool'], "10.0.0.100 - 10.0.0.200")

        options = {opt['name']: opt['data'] for opt in subnet['option-data']}
        self.assertEqual(options['routers'], "10.0.0.1")
        self.assertEqual(options['domain-name-servers'], "8.8.8.8")

    def test_systemd_dhcp_disabled(self):
        vlan = {
            "id": 30,
            "cidr": "172.16.0.1/24",
            "dhcp": True
        }
        self.manager.add_vlan(vlan)
        # We need a dummy parent config for generation to work
        with open(os.path.join(Config.NETWORK_DIR, '10-br0.network'), 'w') as f:
            f.write("[Match]\nName=br0")

        self.manager.generate_systemd_config()

        network_file = os.path.join(Config.NETWORK_DIR, '20-vlan30.network')
        with open(network_file, 'r') as f:
            content = f.read()
            self.assertIn("DHCPServer=no", content)

if __name__ == '__main__':
    unittest.main()
