# core/storage.py
import json
from config import config


class Storage:
    def __init__(self):
        self.config_path = config.FILE_DATA

    def load_data(self):
        with open(self.config_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def write_data(self, data):
        with open(self.config_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

storage = Storage()
