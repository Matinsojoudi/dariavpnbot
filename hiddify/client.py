import sqlite3
import requests
import json
from datetime import datetime, timedelta
from env import settings as app_settings
from env import settings
from hiddify.exceptions import (
    HiddifyAPIError,
    HiddifyAuthError,
    HiddifyConnectionError,
    HiddifyNotFoundError,
)
from pyxui import XUI
from pyxui.errors import BadLogin
import urllib3
urllib3.disable_warnings()

# Monkeypatch pyxui to always use verify=False to bypass self-signed SSL verification failures
def _patch_pyxui():
    import pyxui
    import requests
    
    def custom_request(self, path: str, method: str, params: dict = None) -> requests.Response:
        if path == "login":
            url = f"{self.full_address}/login"
        else:
            url = f"{self.full_address}/{self.api_path}/inbounds/{path}"

        if self.session_string:
            cookie = {self.cookie_name: self.session_string}
        else:
            cookie = None

        if method == "GET":
            response = requests.get(url, cookies=cookie, verify=False)
        elif method == "POST":
            response = requests.post(url, cookies=cookie, data=params, verify=False)

        return response

    pyxui.XUI.request = custom_request

_patch_pyxui()

class HiddifyClient:
    """XUI/Sanaeii Panel Client Bridge behaving like HiddifyClient."""

    def __init__(self, base_url=None, username=None, password=None, inbound_id=None):
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.inbound_ids = []
        if inbound_id:
            try:
                self.inbound_ids = [int(x.strip()) for x in str(inbound_id).split(',') if x.strip()]
            except ValueError:
                self.inbound_ids = [1]
        self.xui = None

    def reload_config(self):
        """Reload panel settings from database, falling back to environment if needed."""
        try:
            with sqlite3.connect(app_settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT key, value FROM bot_settings WHERE key IN ('XUI_PANEL_URL', 'XUI_USERNAME', 'XUI_PASSWORD', 'XUI_INBOUND_ID')")
                rows = dict(c.fetchall())
                
            db_url = rows.get('XUI_PANEL_URL', '')
            db_user = rows.get('XUI_USERNAME', '')
            db_pass = rows.get('XUI_PASSWORD', '')
            db_inbound_id = rows.get('XUI_INBOUND_ID', '1')

            if db_url:
                self.base_url = db_url.strip().rstrip("/")
            if db_user:
                self.username = db_user.strip()
            if db_pass:
                self.password = db_pass.strip()
                
            if db_inbound_id:
                try:
                    self.inbound_ids = [int(x.strip()) for x in str(db_inbound_id).split(',') if x.strip()]
                except ValueError:
                    self.inbound_ids = [1]
            else:
                self.inbound_ids = [1]
            
            if self.base_url and self.username and self.password:
                https = self.base_url.startswith("https")
                self.xui = XUI(full_address=self.base_url, panel="sanaei", https=https)
                try:
                    self.xui.login(self.username, self.password)
                except BadLogin as e:
                    print("XUI Panel Login failed (Bad credentials):", e)
                    self.xui = None
                except Exception as e:
                    print(f"XUI Connection failed: {e}")
                    self.xui = None
        except Exception as e:
            print("Error reloading config:", e)

    def _find_client(self, uuid):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return None, None, None
            
        try:
            inbounds = self.xui.get_inbounds()
            if not inbounds or 'obj' not in inbounds:
                return None, None, None
                
            first_inbound_id = None
            first_client = None
            total_up = 0
            total_down = 0
            found = False
            
            for inbound in inbounds['obj']:
                inbound_id = inbound['id']
                settings_str = inbound.get('settings', '{}')
                try:
                    settings = json.loads(settings_str)
                except Exception:
                    continue
                    
                clients = settings.get('clients', [])
                for client in clients:
                    if client.get('id') == uuid or client.get('email') == uuid:
                        found = True
                        if first_client is None:
                            first_inbound_id = inbound_id
                            first_client = client
                            
                        email = client.get('email')
                        for stat in inbound.get('clientStats', []):
                            if stat.get('email') == email:
                                total_up += stat.get('up', 0)
                                total_down += stat.get('down', 0)
                                break
                                
            if found:
                aggregated_stat = {
                    "up": total_up,
                    "down": total_down
                }
                return first_inbound_id, first_client, aggregated_stat
        except Exception as e:
            print("Error finding client in XUI:", e)
        return None, None, None

    def list_users(self):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return []
            
        try:
            inbounds = self.xui.get_inbounds()
            if not inbounds or 'obj' not in inbounds:
                return []
                
            users_list = []
            seen_uuids = set()
            for inbound in inbounds['obj']:
                settings_str = inbound.get('settings', '{}')
                try:
                    settings = json.loads(settings_str)
                except Exception:
                    continue
                for client in settings.get('clients', []):
                    uuid = client.get('id')
                    if uuid and uuid not in seen_uuids:
                        seen_uuids.add(uuid)
                        users_list.append({
                            "name": client.get('email', 'Unknown'),
                            "uuid": uuid
                        })
            return users_list
        except Exception as e:
            print("Error listing users from XUI:", e)
        return []

    def get_user(self, uuid):
        inbound_id, client, stat = self._find_client(uuid)
        if not client:
            return {}
            
        total_bytes = client.get('totalGB', 0)
        limit_gb = float(total_bytes) / (1024**3) if total_bytes else 0.0
        
        up = stat.get('up', 0) if stat else 0
        down = stat.get('down', 0) if stat else 0
        used_gb = float(up + down) / (1024**3)
        
        expiry = client.get('expiryTime', 0)
        start_date = None
        if expiry < 0:
            package_days = abs(expiry) // (24 * 3600 * 1000)
        elif expiry > 0:
            rem_seconds = (expiry / 1000.0) - datetime.now().timestamp()
            package_days = max(0, int(rem_seconds // (24 * 3600)))
            start_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            package_days = 0
            
        return {
            "name": client.get('email', 'Unknown'),
            "uuid": uuid,
            "usage_limit_GB": limit_gb,
            "current_usage_GB": used_gb,
            "package_days": package_days,
            "start_date": start_date,
            "enable": client.get('enable', True)
        }

    def create_user(self, payload):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return None
            
        uuid = payload.get("uuid")
        email = payload.get("name")
        enable = payload.get("enable", True)
        total_gb = int(payload.get("usage_limit_GB", 0) * 1024 * 1024 * 1024)
        expire_time = -int(payload.get("package_days", 0) * 24 * 3600 * 1000)
        
        # Build comment/telegram_id string
        tg_id = payload.get("telegram_id")
        comment = payload.get("comment")
        parts = []
        if tg_id:
            parts.append(f"TG:{tg_id}")
        if comment:
            parts.append(comment)
        final_tg_id = " | ".join(parts) if parts else ""
        
        last_res = None
        for inbound_id in self.inbound_ids:
            try:
                last_res = self.xui.add_client(
                    inbound_id=inbound_id,
                    email=email,
                    uuid=uuid,
                    enable=enable,
                    flow="",
                    limit_ip=0,
                    total_gb=total_gb,
                    expire_time=expire_time,
                    telegram_id=final_tg_id,
                    subscription_id=uuid
                )
            except Exception as e:
                print(f"Error adding client to inbound {inbound_id}: {e}")
        return last_res

    def update_user(self, uuid, payload):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return None
            
        inbound_id, client, stat = self._find_client(uuid)
        if not client:
            return {}
            
        email = payload.get("name", client.get("email"))
        enable = payload.get("enable", client.get("enable", True))
        flow = payload.get("flow", client.get("flow", ""))
        limit_ip = payload.get("limit_ip", client.get("limitIp", 0))
        
        tg_id = payload.get("telegram_id")
        comment = payload.get("comment")
        if tg_id or comment:
            parts = []
            if tg_id:
                parts.append(f"TG:{tg_id}")
            if comment:
                parts.append(comment)
            telegram_id = " | ".join(parts)
        else:
            telegram_id = client.get("tgId", "")
            
        subscription_id = client.get("subId", uuid)
        
        if "usage_limit_GB" in payload:
            total_gb = int(payload["usage_limit_GB"] * 1024 * 1024 * 1024)
        else:
            total_gb = client.get("totalGB", 0)
            
        if "package_days" in payload:
            curr_expiry = client.get("expiryTime", 0)
            if curr_expiry > 0:
                expire_time = int((datetime.now().timestamp() + payload["package_days"] * 24 * 3600) * 1000)
            else:
                expire_time = -int(payload["package_days"] * 24 * 3600 * 1000)
        else:
            expire_time = client.get("expiryTime", 0)
            
        last_res = None
        for inbound_id in self.inbound_ids:
            try:
                last_res = self.xui.update_client(
                    inbound_id=inbound_id,
                    email=email,
                    uuid=uuid,
                    enable=enable,
                    flow=flow,
                    limit_ip=limit_ip,
                    total_gb=total_gb,
                    expire_time=expire_time,
                    telegram_id=telegram_id,
                    subscription_id=subscription_id
                )
            except Exception as e:
                print(f"Error updating client in inbound {inbound_id}: {e}")
        return last_res

    def delete_user(self, uuid):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return False
            
        deleted = False
        for inbound_id in self.inbound_ids:
            try:
                self.xui.delete_client(inbound_id=inbound_id, uuid=uuid)
                deleted = True
            except Exception as e:
                print(f"Error deleting client from inbound {inbound_id}: {e}")
        return deleted

    def reset_user_usage(self, uuid):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return {}
            
        res = {}
        for inbound_id in self.inbound_ids:
            try:
                res = self.xui.reset_client_traffic(inbound_id=inbound_id, uuid=uuid)
            except Exception as e:
                print(f"Error resetting client traffic in inbound {inbound_id}: {e}")
        return res

    def get_user_usage(self, uuid):
        inbound_id, client, stat = self._find_client(uuid)
        if not stat:
            return {"usage": 0.0}
        up = stat.get('up', 0)
        down = stat.get('down', 0)
        return {"usage": float(up + down) / (1024**3)}

    def get_sub_link(self, uuid, name=None):
        sub_base = "https://sus.ananasino.icu/sus"
        try:
            with sqlite3.connect(app_settings.database) as conn:
                c = conn.cursor()
                c.execute("SELECT value FROM bot_settings WHERE key = 'SUB_BASE_URL'")
                row = c.fetchone()
                if row and row[0]:
                    sub_base = row[0].strip().rstrip("/")
        except:
            pass
            
        sub_url = f"{sub_base}/{uuid}"
        if name:
            sub_url += f"#{name}"
        return sub_url

    def get_stats(self):
        if not self.xui:
            self.reload_config()
        if not self.xui:
            return {}
            
        try:
            cookies = {self.xui.cookie_name: self.xui.session_string}
            url = f"{self.xui.full_address}/server/sysopt"
            resp = requests.post(url, cookies=cookies, verify=False, timeout=10)
            if resp.status_code == 405 or resp.status_code == 404:
                resp = requests.get(url, cookies=cookies, verify=False, timeout=10)
            
            data = resp.json()
            if data.get('success'):
                obj = data.get('obj', {})
                cpu = obj.get('cpu', 0)
                cores = obj.get('cores', 1)
                mem = obj.get('mem', {})
                disk = obj.get('disk', {})
                net = obj.get('net', {})
                load = obj.get('load', {})
                
                mem_used_gb = float(mem.get('used', mem.get('current', 0))) / (1024**3)
                mem_total_gb = float(mem.get('total', 1)) / (1024**3)
                disk_used_gb = float(disk.get('used', disk.get('current', 0))) / (1024**3)
                disk_total_gb = float(disk.get('total', 1)) / (1024**3)
                
                # Fetch xray clients traffic stats
                xray_used_bytes = 0
                seen_emails = set()
                try:
                    inbounds = self.xui.get_inbounds()
                    for ib in inbounds:
                        for stat in ib.get('clientStats', []):
                            xray_used_bytes += stat.get('up', 0) + stat.get('down', 0)
                            email = stat.get('email')
                            if email:
                                seen_emails.add(email)
                except Exception as ex:
                    print("Error getting client stats for traffic sum:", ex)
                
                xray_used_gb = float(xray_used_bytes) / (1024**3)
                
                return {
                    "stats": {
                        "system": {
                            "cpu_percent": cpu,
                            "num_cpus": cores,
                            "ram_used": mem_used_gb,
                            "ram_total": mem_total_gb,
                            "disk_used": disk_used_gb,
                            "disk_total": disk_total_gb,
                            "hiddify_used": xray_used_gb,
                            "load_avg_1min": load.get('1', '—'),
                            "load_avg_5min": load.get('5', '—'),
                            "load_avg_15min": load.get('15', '—'),
                            "bytes_recv": net.get('up', 0),
                            "bytes_sent": net.get('down', 0),
                            "net_total_cumulative_GB": (net.get('up', 0) + net.get('down', 0)) / (1024**3),
                            "total_connections": obj.get('xray', {}).get('connections', obj.get('tcp', 0) + obj.get('udp', 0)),
                            "total_unique_ips": len(seen_emails)
                        },
                        "top5": {}
                    },
                    "usage_history": {
                        "total": {
                            "users": len(seen_emails),
                            "usage": xray_used_bytes
                        }
                    }
                }
        except Exception as e:
            print("Error getting system stats from XUI:", e)
        return {}

# Singleton instance for backwards compatibility
hiddify_client = HiddifyClient()
