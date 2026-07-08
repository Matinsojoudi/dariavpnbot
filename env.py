import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.bot_id = os.getenv('BOT_ID')
        self.bot_link = os.getenv('BOT_LINK')
        self.customers_starts_2 = os.getenv('CUSTOMERS_STARTS_2')
        self.matin = os.getenv('MATIN')
        self.token = os.getenv('TOKEN')
        self.admin_list = list(map(int, os.getenv('ADMIN_LIST').split(',')))  # Convert admin IDs to integers
        self.admin = os.getenv('ADMIN')
        self.database = os.getenv('DATABASE')
        
        # Hiddify Configs
        self.hiddify_panel_url = os.getenv('HIDDIFY_PANEL_URL', '')
        self.hiddify_proxy_path = os.getenv('HIDDIFY_PROXY_PATH', '')
        self.hiddify_api_key = os.getenv('HIDDIFY_API_KEY', '')
        # SOCKS Proxy fallback
        self.socks_proxy = os.getenv('SOCKS_PROXY', '')

settings = Settings()
