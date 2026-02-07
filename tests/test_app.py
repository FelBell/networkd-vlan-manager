import unittest
import json
import os
import shutil
from vlan_manager.config import Config
from vlan_manager.app import app as app_module
from vlan_manager.core import VlanManager

class TestVlanApp(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'test_app_data'
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        self.original_data_file = Config.DATA_FILE
        self.original_network_dir = Config.NETWORK_DIR
        self.original_nftables_dir = Config.NFTABLES_DIR

        Config.DATA_FILE = os.path.join(self.test_dir, 'vlans.json')
        Config.NETWORK_DIR = os.path.join(self.test_dir, 'network')
        Config.NFTABLES_DIR = os.path.join(self.test_dir, 'nftables')
        Config.PARENT_INTERFACE = 'br0'
        Config.WAN_INTERFACE = 'eth0'

        app_module.vlan_manager = VlanManager()

        self.app = app_module.app.test_client()
        self.app.testing = True

        with self.app.session_transaction() as sess:
            sess['logged_in'] = True

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        Config.DATA_FILE = self.original_data_file
        Config.NETWORK_DIR = self.original_network_dir
        Config.NFTABLES_DIR = self.original_nftables_dir

    def test_get_vlans(self):
        response = self.app.get('/api/vlans')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_add_vlan(self):
        data = {
            "id": 40,
            "cidr": "192.168.40.1/24",
            "dhcp": True,
            "dhcp_start": "192.168.40.100",
            "dhcp_end": "192.168.40.200",
            "nat": False
        }
        response = self.app.post('/api/vlans', json=data)
        self.assertEqual(response.status_code, 201)

        response = self.app.get('/api/vlans')
        self.assertEqual(len(response.json), 1)
        self.assertEqual(response.json[0]['id'], 40)
        self.assertEqual(response.json[0]['dhcp_start'], "192.168.40.100")

    def test_add_vlan_with_dns(self):
        data = {
            "id": 41,
            "cidr": "192.168.41.1/24",
            "dhcp": True,
            "dhcp_start": "192.168.41.100",
            "dhcp_end": "192.168.41.200",
            "dns_servers": "8.8.8.8, 8.8.4.4",
            "nat": False
        }
        response = self.app.post('/api/vlans', json=data)
        self.assertEqual(response.status_code, 201)

        response = self.app.get('/api/vlans')
        vlan = next(v for v in response.json if v['id'] == 41)
        self.assertEqual(vlan['dns_servers'], "8.8.8.8, 8.8.4.4")

    def test_add_vlan_invalid(self):
        data = {
            "id": "invalid",
            "cidr": "bad"
        }
        response = self.app.post('/api/vlans', json=data)
        self.assertEqual(response.status_code, 400)

    def test_dashboard(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VLAN Manager', response.data)
        self.assertIn(b'Add New VLAN', response.data)

if __name__ == '__main__':
    unittest.main()
