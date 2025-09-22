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
            import os
            # Windows系统使用不同的配置目录
            if os.name == 'nt':  # Windows
                self.config_dir = Path(os.environ.get('APPDATA', Path.home())) / 'GeneticImprove'
            else:  # macOS/Linux
                self.config_dir = Path.home() / '.genetic_improve'

            self.config_file = self.config_dir / 'settings.json'

            # 设置默认项目存储路径
            # Windows: Documents文件夹
            # macOS: Documents文件夹
            documents_path = Path.home() / 'Documents' / 'GeneticImprove'
            self.default_storage = str(documents_path)

            # 确保默认存储目录存在
            try:
                documents_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                # 如果无法创建，使用用户主目录
                print(f"无法创建默认目录 {documents_path}: {e}")
                self.default_storage = str(Path.home() / 'GeneticImprove')
                Path(self.default_storage).mkdir(parents=True, exist_ok=True)

            self.load_settings()
            self._initialized = True

    def load_settings(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True)

        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                stored_path = settings.get('default_storage', self.default_storage)

                # 验证存储的路径是否有效
                # 排除网络路径和无效路径
                if stored_path and not stored_path.startswith('//'):
                    try:
                        path = Path(stored_path)
                        # 确保路径存在或可以创建
                        if path.exists() or not path.is_absolute():
                            self.default_storage = stored_path
                        else:
                            # 尝试创建目录
                            path.mkdir(parents=True, exist_ok=True)
                            self.default_storage = stored_path
                    except Exception as e:
                        print(f"存储的路径无效 {stored_path}: {e}")
                        # 使用默认路径（保持初始化时设置的值）
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