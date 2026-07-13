import os
from dotenv import load_dotenv

load_dotenv()

def _parse_int_list(raw):
    if not raw:
        return []
    result = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue
    return result


class Settings:
    def __init__(self):
        self.bot_id = os.getenv('BOT_ID')
        self.bot_link = os.getenv('BOT_LINK')
        self.customers_starts_2 = os.getenv('CUSTOMERS_STARTS_2')
        self.matin = os.getenv('MATIN')
        self.token = os.getenv('TOKEN')
        self.admin_list = _parse_int_list(os.getenv('ADMIN_LIST'))
        self.admin = os.getenv('ADMIN')
        self.database = os.getenv('DATABASE') or 'dariavpnbot.db'
        
        # Hiddify Configs (legacy; runtime panel uses X-UI keys in bot_settings)
        self.hiddify_panel_url = os.getenv('HIDDIFY_PANEL_URL', '')
        self.hiddify_proxy_path = os.getenv('HIDDIFY_PROXY_PATH', '')
        self.hiddify_api_key = os.getenv('HIDDIFY_API_KEY', '')
        # SOCKS Proxy fallback
        self.socks_proxy = os.getenv('SOCKS_PROXY', '')

settings = Settings()
