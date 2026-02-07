import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-me'
    PARENT_INTERFACE = os.environ.get('PARENT_INTERFACE', 'br0')
    WAN_INTERFACE = os.environ.get('WAN_INTERFACE', 'eth0')
    DATA_FILE = os.environ.get('DATA_FILE', 'vlan_manager/data/vlans.json')
    NETWORK_DIR = os.environ.get('NETWORK_DIR', '/etc/systemd/network')
    NFTABLES_DIR = os.environ.get('NFTABLES_DIR', '/etc/nftables.d')
    NFTABLES_INCLUDE_FILE = 'vlans.nft'
    KEA_CONF_FILE = os.environ.get('KEA_CONF_FILE', '/etc/kea/kea-dhcp4.conf')
    KEA_SERVICE_NAME = os.environ.get('KEA_SERVICE_NAME', 'kea-dhcp4-server')
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')
