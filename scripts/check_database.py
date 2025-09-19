"""
检查数据库表和数据
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER,
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME
)

def check_database():
    """检查数据库表和数据"""
    engine = create_engine(
        f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
        f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
    )

    with engine.connect() as connection:
        # 检查邀请码表是否存在
        result = connection.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = :database_name
            AND table_name = 'invitation_codes'
        """), {"database_name": CLOUD_DB_NAME})

        table_exists = result.fetchone()[0] > 0
        print(f"邀请码表存在: {table_exists}")

        if table_exists:
            # 查看邀请码数据
            result = connection.execute(text("SELECT * FROM invitation_codes"))
            codes = result.fetchall()
            print(f"邀请码数量: {len(codes)}")
            for code in codes:
                print(f"- {code}")

        # 检查用户表
        result = connection.execute(text("SELECT COUNT(*) FROM `id-pw`"))
        user_count = result.fetchone()[0]
        print(f"\n用户数量: {user_count}")

if __name__ == "__main__":
    check_database()