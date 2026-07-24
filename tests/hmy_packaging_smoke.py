"""PyInstaller 冻结环境下的慧牧云登录令牌冒烟测试。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from api.api_client import get_api_client
from api.hmy_api_client import HMYApiClient
from auth.token_manager import TokenManager


def main() -> None:
    test_token = "packaged-login-token"
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["HOME"] = temp_dir
        data_dir = Path(temp_dir)
        manager = TokenManager()
        manager.data_dir = data_dir
        manager.token_file = data_dir / "token_cache.json"
        if not manager.save_token(test_token, "10075345"):
            raise RuntimeError("打包环境无法保存登录令牌")

        reloaded_manager = TokenManager()
        reloaded_manager.data_dir = data_dir
        reloaded_manager.token_file = manager.token_file
        if reloaded_manager.get_token() != test_token:
            raise RuntimeError("打包环境重启后无法恢复登录令牌")

        get_api_client().token = test_token
        if HMYApiClient._load_auth_token() != test_token:
            raise RuntimeError("慧牧云未复用当前登录会话令牌")

    print("HMY_PACKAGING_SMOKE_OK")


if __name__ == "__main__":
    main()
