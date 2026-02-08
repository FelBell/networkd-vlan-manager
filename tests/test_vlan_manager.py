import unittest
import os
import shutil
import json
from unittest.mock import patch, MagicMock
from vlan_manager.core import VlanManager
from vlan_manager.config import Config

class TestVlanManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_data'
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        self.original_data_file = Config.DATA_FILE
        self.original_network_dir = Config.NETWORK_DIR
        self.original_nftables_dir = Config.NFTABLES_DIR
        self.original_kea_config = Config.KEA_CONFIG_FILE

        Config.DATA_FILE = os.path.join(self.test_dir, 'vlans.json')
        Config.NETWORK_DIR = os.path.join(self.test_dir, 'network')
        Config.NFTABLES_DIR = os.path.join(self.test_dir, 'nftables')
        Config.KEA_CONFIG_FILE = os.path.join(self.test_dir, 'kea/kea-dhcp4.conf')
        Config.PARENT_INTERFACE = 'br0'
        Config.WAN_INTERFACE = 'eth0'

        os.makedirs(Config.NETWORK_DIR, exist_ok=True)
        # Create a dummy parent config to test discovery
        with open(os.path.join(Config.NETWORK_DIR, '25-my-bridge.network'), 'w') as f:
            f.write('[Match]\nName=br0\n\n[Network]\nDHCP=yes\n')

        self.manager = VlanManager()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        Config.DATA_FILE = self.original_data_file
        Config.NETWORK_DIR = self.original_network_dir
        Config.NFTABLES_DIR = self.original_nftables_dir
        Config.KEA_CONFIG_FILE = self.original_kea_config

    def test_add_vlan(self):
        vlan = {
            "id": 10,
            "cidr": "192.168.10.1/24",
            "dhcp": True,
            "forwarding": True,
            "nat": True
        }
        self.manager.add_vlan(vlan)
        vlans = self.manager.get_vlans()
        self.assertEqual(len(vlans), 1)
        self.assertEqual(vlans[0]['id'], 10)

        with self.assertRaises(ValueError):
            self.manager.add_vlan(vlan)

    def test_add_vlan_invalid_cidr(self):
        vlan = {
            "id": 50,
            "cidr": "invalid-cidr",
            "dhcp": True,
            "nat": True
        }
        with self.assertRaises(ValueError):
            self.manager.add_vlan(vlan)

    def test_generate_config(self):
        vlan = {
            "id": 20,
            "cidr": "10.0.0.1/24",
            "dhcp": False,
            "forwarding": False,
            "nat": True
        }
        self.manager.add_vlan(vlan)
        self.manager.generate_systemd_config()

        netdev_path = os.path.join(Config.NETWORK_DIR, '20-vlan20.netdev')
        self.assertTrue(os.path.exists(netdev_path))
        with open(netdev_path, 'r') as f:
            content = f.read()
            self.assertIn('Name=vlan20', content)
            self.assertIn('Kind=vlan', content)
            self.assertIn('Id=20', content)

        network_path = os.path.join(Config.NETWORK_DIR, '20-vlan20.network')
        self.assertTrue(os.path.exists(network_path))
        with open(network_path, 'r') as f:
            content = f.read()
            self.assertIn('Address=10.0.0.1/24', content)
            self.assertIn('DHCPServer=no', content)
            self.assertIn('IPMasquerade=yes', content)
            self.assertIn('IPForward=no', content)

        # Should detect '25-my-bridge.network' as parent config
        dropin_path = os.path.join(Config.NETWORK_DIR, '25-my-bridge.network.d', 'vlan-20.conf')
        self.assertTrue(os.path.exists(dropin_path))
        with open(dropin_path, 'r') as f:
            content = f.read()
            self.assertIn('VLAN=vlan20', content)

    def test_nftables_generation(self):
        vlan = {
            "id": 30,
            "cidr": "172.16.0.1/24",
            "dhcp": True,
            "forwarding": True,
            "nat": True
        }
        self.manager.add_vlan(vlan)
        filepath = self.manager.generate_nftables_config()

        self.assertTrue(os.path.exists(filepath))
        with open(filepath, 'r') as f:
            content = f.read()
            self.assertIn('table inet vlan_mgmt', content)
            self.assertIn('chain postrouting', content)
            self.assertIn('masquerade', content)
            self.assertIn('172.16.0.1/24', content)

    @patch('subprocess.run')
    def test_apply_config(self, mock_run):
        with patch('builtins.open', unittest.mock.mock_open()):
             self.manager.apply_config()

        self.assertTrue(mock_run.called)

        calls = [args[0] for args, kwargs in mock_run.call_args_list]
        has_sysctl = any('sysctl' in cmd[0] for cmd in calls)
        self.assertTrue(has_sysctl)

if __name__ == '__main__':
    unittest.main()
