"""
创建邀请码表的脚本
"""

from sqlalchemy import create_engine, text
from core.data.update_manager import (
    CLOUD_DB_HOST, CLOUD_DB_PORT, CLOUD_DB_USER,
    CLOUD_DB_PASSWORD, CLOUD_DB_NAME
)

def create_invitation_table():
    """创建邀请码表"""
    engine = create_engine(
        f"mysql+pymysql://{CLOUD_DB_USER}:{CLOUD_DB_PASSWORD}"
        f"@{CLOUD_DB_HOST}:{CLOUD_DB_PORT}/{CLOUD_DB_NAME}?charset=utf8mb4"
    )

    with engine.connect() as connection:
        # 检查表是否已存在
        result = connection.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = :database_name
            AND table_name = 'invitation_codes'
        """), {"database_name": CLOUD_DB_NAME})

        if result.fetchone()[0] > 0:
            print("邀请码表已存在")
            return

        # 创建邀请码表
        connection.execute(text("""
            CREATE TABLE invitation_codes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                code VARCHAR(20) NOT NULL UNIQUE,
                status TINYINT DEFAULT 1 COMMENT '1-有效, 0-无效',
                max_uses INT DEFAULT 1 COMMENT '最大使用次数',
                current_uses INT DEFAULT 0 COMMENT '当前使用次数',
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expire_time TIMESTAMP NULL COMMENT '过期时间，NULL表示永不过期',
                description VARCHAR(255) COMMENT '邀请码描述'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邀请码表'
        """))

        # 插入一些测试邀请码
        connection.execute(text("""
            INSERT INTO invitation_codes (code, max_uses, description) VALUES
            ('YILI2025', 100, '伊利2025年内部邀请码'),
            ('TEST001', 10, '测试邀请码1'),
            ('ADMIN888', 50, '管理员邀请码')
        """))

        connection.commit()
        print("邀请码表创建成功，并插入了测试数据")

if __name__ == "__main__":
    create_invitation_table()