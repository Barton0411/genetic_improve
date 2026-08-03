#!/usr/bin/env python3
"""创建首次改密状态表，并只将迁移前已有本地账号标记为待改密。"""

import argparse
import os
import urllib.parse
from pathlib import Path

from sqlalchemy import create_engine, text


def load_env_file(path: Path) -> None:
    """读取简单 KEY=VALUE 环境文件，不执行 shell 内容。"""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def database_url() -> str:
    password = os.environ["DB_PASSWORD"]
    host = os.environ.get("DB_HOST", "defectgene-new.mysql.polardb.rds.aliyuncs.com")
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("DB_USER", "defect_genetic_checking")
    name = os.environ.get("DB_NAME", "bull_library")
    return (
        f"mysql+pymysql://{user}:{urllib.parse.quote_plus(password)}"
        f"@{host}:{port}/{name}?charset=utf8mb4"
    )


def migrate(engine) -> tuple[int, int]:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS auth_password_state (
                    user_id VARCHAR(191) NOT NULL PRIMARY KEY,
                    must_change_password TINYINT(1) NOT NULL DEFAULT 1,
                    password_changed_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT IGNORE INTO auth_password_state (user_id, must_change_password)
                SELECT ID, 1 FROM `id-pw`
                """
            )
        )
        account_count = connection.execute(
            text("SELECT COUNT(*) FROM `id-pw`")
        ).scalar_one()
        pending_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM auth_password_state WHERE must_change_password=1"
            )
        ).scalar_one()
    return int(account_count), int(pending_count)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file:
        load_env_file(args.env_file)
    accounts, pending = migrate(create_engine(database_url(), echo=False))
    print(f"accounts={accounts}")
    print(f"pending_password_changes={pending}")


if __name__ == "__main__":
    main()
