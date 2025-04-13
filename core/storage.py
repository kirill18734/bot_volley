# core/storage.py
import json
import asyncio
from config import config


class Storage:
    def __init__(self):
        self.config_path = config.FILE_DATA

    async def load_data(self):
        return await asyncio.to_thread(self._load_data_sync)

    def _load_data_sync(self):
        with open(self.config_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    async def write_data(self, data):
        return await asyncio.to_thread(self._save_data_sync, data)

    def _save_data_sync(self, data):
        with open(self.config_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)


storage = Storage()
