# config/settings.py
from pathlib import Path
import json

class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.config_dir = Path.home() / '.genetic_improve'
            self.config_file = self.config_dir / 'settings.json'
            self.default_storage = str(Path.home() / 'Documents' / 'GeneticImprove')
            self.load_settings()
            self._initialized = True

    def load_settings(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)
        
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.default_storage = settings.get('default_storage', self.default_storage)
        else:
            self.save_settings()

    def save_settings(self):
        settings = {
            'default_storage': self.default_storage
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def get_default_storage(self):
        return self.default_storage

    def set_default_storage(self, path):
        self.default_storage = str(path)
        self.save_settings()