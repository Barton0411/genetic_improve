#!/usr/bin/env python3
"""
更新数据库表结构，添加强制更新支持
"""

import pymysql
import json
import logging
import os

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库连接配置 - 更新为环境变量模式
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'defectgene-new.mysql.polardb.rds.aliyuncs.com'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'defect_genetic_checking'),
    'password': os.getenv('DB_PASSWORD'),  # 从环境变量获取，不再硬编码
    'database': os.getenv('DB_NAME', 'bull_library'),
    'charset': 'utf8mb4'
}

def connect_database():
    """连接数据库"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        logger.info("数据库连接成功")
        return connection
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def update_table_schema(connection):
    """更新app_versions表结构"""
    try:
        cursor = connection.cursor()
        
        # 1. 检查表是否存在
        cursor.execute("SHOW TABLES LIKE 'app_versions'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            logger.info("创建app_versions表...")
            create_table_sql = """
            CREATE TABLE app_versions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(20) NOT NULL UNIQUE,
                release_date DATETIME NOT NULL,
                is_latest TINYINT DEFAULT 0,
                changes TEXT,
                mac_download_url TEXT,
                win_download_url TEXT,
                linux_download_url TEXT,
                force_update TINYINT DEFAULT 0,
                security_update TINYINT DEFAULT 0,
                min_supported_version VARCHAR(20),
                package_size BIGINT DEFAULT 0,
                mac_md5 VARCHAR(32),
                win_md5 VARCHAR(32),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            cursor.execute(create_table_sql)
            logger.info("✅ app_versions表创建成功")
        else:
            logger.info("app_versions表已存在，检查是否需要添加新字段...")
            
            # 2. 检查并添加新字段
            new_fields = [
                ('force_update', 'TINYINT DEFAULT 0', '强制更新标志'),
                ('security_update', 'TINYINT DEFAULT 0', '安全更新标志'),
                ('min_supported_version', 'VARCHAR(20)', '最低支持版本'),
                ('package_size', 'BIGINT DEFAULT 0', '安装包大小'),
                ('mac_md5', 'VARCHAR(32)', 'Mac版MD5'),
                ('win_md5', 'VARCHAR(32)', 'Windows版MD5'),
                ('linux_download_url', 'TEXT', 'Linux下载链接'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP', '更新时间')
            ]
            
            for field_name, field_type, description in new_fields:
                try:
                    # 检查字段是否存在
                    cursor.execute(f"SHOW COLUMNS FROM app_versions LIKE '{field_name}'")
                    field_exists = cursor.fetchone()
                    
                    if not field_exists:
                        cursor.execute(f"ALTER TABLE app_versions ADD COLUMN {field_name} {field_type}")
                        logger.info(f"✅ 已添加字段: {field_name} ({description})")
                    else:
                        logger.info(f"⏭️  字段已存在: {field_name}")
                except Exception as e:
                    logger.warning(f"添加字段 {field_name} 失败: {e}")
        
        connection.commit()
        cursor.close()
        logger.info("✅ 数据库表结构更新完成")
        
    except Exception as e:
        logger.error(f"更新表结构失败: {e}")
        connection.rollback()

def insert_test_version(connection):
    """插入测试版本数据"""
    try:
        cursor = connection.cursor()
        
        # 准备1.0.6版本的测试数据
        version_data = {
            'version': '1.0.6',
            'release_date': '2025-09-16 22:00:00',
            'is_latest': 1,
            'changes': json.dumps([
                '🔒 重要安全修复：修复数据泄露漏洞',
                '🚨 紧急修复：修复程序崩溃问题',
                '⚡ 性能优化：提升系统运行速度30%',
                '💾 新增功能：增强数据备份机制',
                '🛡️ 系统加固：增强防护能力',
                '🔄 智能更新：支持程序内自动更新'
            ], ensure_ascii=False),
            'mac_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_mac.dmg',
            'win_download_url': 'https://genetic-improve.oss-cn-beijing.aliyuncs.com/releases/v1.0.6/GeneticImprove_v1.0.6_win.exe',
            'force_update': 1,  # 强制更新
            'security_update': 1,  # 安全更新
            'min_supported_version': '1.0.5',  # 最低支持版本
            'package_size': 52428800,  # 50MB
            'mac_md5': 'abc123def456789',
            'win_md5': 'def456abc123789'
        }
        
        # 先将旧版本设为非最新
        cursor.execute("UPDATE app_versions SET is_latest = 0")
        
        # 检查版本是否已存在
        cursor.execute("SELECT id FROM app_versions WHERE version = %s", (version_data['version'],))
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有版本
            update_sql = """
            UPDATE app_versions SET
                release_date = %(release_date)s,
                is_latest = %(is_latest)s,
                changes = %(changes)s,
                mac_download_url = %(mac_download_url)s,
                win_download_url = %(win_download_url)s,
                force_update = %(force_update)s,
                security_update = %(security_update)s,
                min_supported_version = %(min_supported_version)s,
                package_size = %(package_size)s,
                mac_md5 = %(mac_md5)s,
                win_md5 = %(win_md5)s
            WHERE version = %(version)s
            """
            cursor.execute(update_sql, version_data)
            logger.info(f"✅ 已更新版本 {version_data['version']} 数据")
        else:
            # 插入新版本
            insert_sql = """
            INSERT INTO app_versions 
            (version, release_date, is_latest, changes, mac_download_url, win_download_url,
             force_update, security_update, min_supported_version, package_size, mac_md5, win_md5)
            VALUES 
            (%(version)s, %(release_date)s, %(is_latest)s, %(changes)s, %(mac_download_url)s, 
             %(win_download_url)s, %(force_update)s, %(security_update)s, %(min_supported_version)s,
             %(package_size)s, %(mac_md5)s, %(win_md5)s)
            """
            cursor.execute(insert_sql, version_data)
            logger.info(f"✅ 已插入新版本 {version_data['version']}")
        
        connection.commit()
        cursor.close()
        
    except Exception as e:
        logger.error(f"插入测试版本失败: {e}")
        connection.rollback()

def verify_database_update(connection):
    """验证数据库更新"""
    try:
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # 查询最新版本信息
        cursor.execute("""
        SELECT version, is_latest, force_update, security_update, 
               min_supported_version, package_size, mac_download_url, win_download_url
        FROM app_versions 
        WHERE is_latest = 1
        """)
        
        latest_version = cursor.fetchone()
        
        if latest_version:
            logger.info("✅ 数据库验证成功，最新版本信息:")
            logger.info(f"   版本号: {latest_version['version']}")
            logger.info(f"   强制更新: {'是' if latest_version['force_update'] else '否'}")
            logger.info(f"   安全更新: {'是' if latest_version['security_update'] else '否'}")
            logger.info(f"   最低支持版本: {latest_version['min_supported_version']}")
            logger.info(f"   安装包大小: {latest_version['package_size']} 字节")
            logger.info(f"   Mac下载链接: {latest_version['mac_download_url']}")
            logger.info(f"   Win下载链接: {latest_version['win_download_url']}")
        else:
            logger.error("❌ 未找到最新版本信息")
        
        cursor.close()
        
    except Exception as e:
        logger.error(f"验证数据库失败: {e}")

def main():
    """主函数"""
    logger.info("🚀 开始更新数据库结构和版本信息...")
    
    connection = connect_database()
    if not connection:
        return
    
    try:
        # 1. 更新表结构
        update_table_schema(connection)
        
        # 2. 插入测试版本
        insert_test_version(connection)
        
        # 3. 验证更新
        verify_database_update(connection)
        
        logger.info("🎉 数据库更新完成！")
        
    finally:
        connection.close()
        logger.info("数据库连接已关闭")

if __name__ == '__main__':
    main()