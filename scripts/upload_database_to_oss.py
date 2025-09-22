#!/usr/bin/env python3
"""
上传数据库文件到阿里云OSS
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def upload_database():
    """上传数据库到OSS"""
    try:
        import oss2

        # OSS配置
        from config.oss_config import (
            OSS_ENDPOINT,
            OSS_BUCKET_NAME,
            OSS_ACCESS_KEY_ID,
            OSS_ACCESS_KEY_SECRET,
            OSS_BASE_URL
        )

        # 检查环境变量
        if not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET:
            print("错误：请设置OSS访问凭证环境变量:")
            print("export OSS_ACCESS_KEY_ID='your-key-id'")
            print("export OSS_ACCESS_KEY_SECRET='your-key-secret'")
            return False

        # 本地数据库文件
        local_db_path = project_root / "data" / "databases" / "bull_library.db"

        if not local_db_path.exists():
            print(f"错误：数据库文件不存在: {local_db_path}")
            return False

        # 获取文件大小
        file_size = local_db_path.stat().st_size / 1024 / 1024  # MB
        print(f"准备上传数据库: {local_db_path}")
        print(f"文件大小: {file_size:.1f} MB")

        # 创建OSS客户端
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

        # OSS路径
        oss_key = "databases/bull_library.db"

        print(f"正在上传到OSS: {oss_key}")

        # 使用分片上传处理大文件
        from oss2 import SizedFileAdapter, determine_part_size
        from oss2.models import PartInfo

        total_size = os.path.getsize(str(local_db_path))
        part_size = determine_part_size(total_size, preferred_size=1024 * 1024 * 10)  # 10MB per part

        # 初始化分片上传
        upload_id = bucket.init_multipart_upload(oss_key).upload_id
        parts = []

        # 上传分片
        with open(local_db_path, 'rb') as f:
            part_number = 1
            offset = 0
            while offset < total_size:
                num_to_upload = min(part_size, total_size - offset)
                result = bucket.upload_part(
                    oss_key,
                    upload_id,
                    part_number,
                    SizedFileAdapter(f, num_to_upload)
                )
                parts.append(PartInfo(part_number, result.etag))

                offset += num_to_upload
                part_number += 1

                # 显示进度
                progress = offset / total_size * 100
                print(f"上传进度: {progress:.1f}% ({offset / 1024 / 1024:.1f} / {total_size / 1024 / 1024:.1f} MB)")

        # 完成分片上传
        bucket.complete_multipart_upload(oss_key, upload_id, parts)

        print(f"✅ 上传成功！")

        # 生成下载URL
        url = f"{OSS_BASE_URL}/{oss_key}"
        print(f"下载URL: {url}")

        # 设置文件为公共读
        bucket.put_object_acl(oss_key, oss2.OBJECT_ACL_PUBLIC_READ)
        print("已设置为公共读权限")

        return True

    except ImportError:
        print("错误：缺少oss2库，请安装：pip install oss2")
        return False
    except Exception as e:
        print(f"❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = upload_database()
    sys.exit(0 if success else 1)