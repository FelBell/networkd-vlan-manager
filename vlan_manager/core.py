import os
import json
import subprocess
import logging
import ipaddress
from .config import Config

logger = logging.getLogger(__name__)

class VlanManager:
    def __init__(self, data_file=None):
        self.data_file = data_file or Config.DATA_FILE
        self.vlans = self.load_vlans()

    def load_vlans(self):
        if not os.path.exists(self.data_file):
            return []
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load VLANs: {e}")
            return []

    def save_vlans(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(self.vlans, f, indent=4)

    def get_vlans(self):
        return self.vlans

    def add_vlan(self, vlan_data):
        try:
            v_id = int(vlan_data['id'])
            if v_id < 1 or v_id > 4094:
                raise ValueError("VLAN ID must be between 1 and 4094")
        except ValueError:
            raise ValueError("Invalid VLAN ID")

        for v in self.vlans:
            if int(v['id']) == v_id:
                raise ValueError(f"VLAN ID {v_id} already exists")

        # Validate CIDR
        try:
            ipaddress.ip_network(vlan_data['cidr'], strict=False)
        except ValueError:
             raise ValueError("Invalid CIDR format")

        vlan_data['id'] = v_id
        vlan_data['dhcp'] = bool(vlan_data.get('dhcp'))
        vlan_data['nat'] = bool(vlan_data.get('nat'))

        self.vlans.append(vlan_data)
        self.save_vlans()

    def delete_vlan(self, vlan_id):
        self.vlans = [v for v in self.vlans if str(v['id']) != str(vlan_id)]
        self.save_vlans()

    def generate_systemd_config(self):
        network_dir = Config.NETWORK_DIR
        os.makedirs(network_dir, exist_ok=True)

        # Find the actual config file for the parent interface
        parent_config_file = self._find_parent_config_file(network_dir, Config.PARENT_INTERFACE)
        parent_dropin_dir = os.path.join(network_dir, f"{parent_config_file}.d")
        os.makedirs(parent_dropin_dir, exist_ok=True)

        self._cleanup_configs(network_dir, parent_dropin_dir)

        for vlan in self.vlans:
            vid = vlan['id']
            name = f"vlan{vid}"

            netdev_content = f"""[NetDev]
Name={name}
Kind=vlan

[VLAN]
Id={vid}
"""
            with open(os.path.join(network_dir, f"10-{name}.netdev"), 'w') as f:
                f.write(netdev_content)

            network_content = f"""[Match]
Name={name}

[Network]
Address={vlan['cidr']}
DHCPServer={'yes' if vlan.get('dhcp') else 'no'}
IPMasquerade=no
IPForward=yes
"""
            with open(os.path.join(network_dir, f"10-{name}.network"), 'w') as f:
                f.write(network_content)

            dropin_content = f"""[Network]
VLAN={name}
"""
            with open(os.path.join(parent_dropin_dir, f"vlan-{vid}.conf"), 'w') as f:
                f.write(dropin_content)

    def _find_parent_config_file(self, network_dir, interface_name):
        # Scan for a .network file that matches Name=interface_name
        if not os.path.exists(network_dir):
            return f"{interface_name}.network"

        for f in os.listdir(network_dir):
            if f.endswith(".network"):
                try:
                    with open(os.path.join(network_dir, f), 'r') as file:
                        content = file.read()
                        # Simple check for Name=interface_name
                        # This is naive but works for standard configs
                        if f"Name={interface_name}" in content:
                            return f
                except:
                    continue
        # Fallback to standard naming convention if not found
        return f"10-{interface_name}.network"

    def _cleanup_configs(self, network_dir, parent_dropin_dir):
        if os.path.exists(network_dir):
            for f in os.listdir(network_dir):
                if f.startswith("10-vlan") and (f.endswith(".netdev") or f.endswith(".network")):
                    try:
                        os.remove(os.path.join(network_dir, f))
                    except OSError:
                        pass

        if os.path.exists(parent_dropin_dir):
             for f in os.listdir(parent_dropin_dir):
                if f.startswith("vlan-") and f.endswith(".conf"):
                    try:
                        os.remove(os.path.join(parent_dropin_dir, f))
                    except OSError:
                        pass

    def generate_nftables_config(self):
        lines = []
        lines.append("table inet vlan_mgmt")
        lines.append("delete table inet vlan_mgmt")
        lines.append("table inet vlan_mgmt {")

        lines.append("  chain forward {")
        lines.append("    type filter hook forward priority 0; policy accept;")
        lines.append("    ct state established,related accept")

        for vlan in self.vlans:
             if vlan.get('nat'):
                 lines.append(f'    iifname "vlan{vlan["id"]}" oifname "{Config.WAN_INTERFACE}" accept')

        lines.append("  }")

        lines.append("  chain postrouting {")
        lines.append("    type nat hook postrouting priority 100; policy accept;")

        for vlan in self.vlans:
            if vlan.get('nat'):
                lines.append(f'    ip saddr {vlan["cidr"]} oifname "{Config.WAN_INTERFACE}" masquerade')

        lines.append("  }")
        lines.append("}")

        nft_dir = Config.NFTABLES_DIR
        os.makedirs(nft_dir, exist_ok=True)
        filepath = os.path.join(nft_dir, Config.NFTABLES_INCLUDE_FILE)

        with open(filepath, 'w') as f:
            f.write("\n".join(lines))

        return filepath

    def apply_config(self):
        try:
            self.generate_systemd_config()
            nft_file = self.generate_nftables_config()

            with open('/etc/sysctl.d/99-vlan-manager.conf', 'w') as f:
                f.write("net.ipv4.ip_forward=1\n")

            subprocess.run(['sysctl', '-p', '/etc/sysctl.d/99-vlan-manager.conf'], check=False)

            try:
                subprocess.run(['networkctl', 'reload'], check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.warning("networkctl not found or failed. Skipping systemd reload (Mocking?).")

            try:
                subprocess.run(['nft', '-f', nft_file], check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.warning("nft command not found or failed. Skipping nftables application.")

        except Exception as e:
            logger.error(f"Failed to apply config: {e}")
            raise
