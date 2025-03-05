from sqlalchemy import create_engine, text
import pandas as pd
import logging
from pathlib import Path
import sys
import re

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从update_manager导入数据库路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.data.update_manager import LOCAL_DB_PATH

def test_bull_query():
    """测试公牛数据库查询"""
    # 要测试的公牛ID
    test_bulls = ['001HO02452', '001HO02478', '001HO02556', '001HO02623']
    
    # 连接数据库
    logging.info(f"连接数据库: {LOCAL_DB_PATH}")
    engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
    
    try:
        with engine.connect() as conn:
            # 1. 检查表结构
            logging.info("检查bull_library表结构")
            columns_info = conn.execute(text("PRAGMA table_info(bull_library)")).fetchall()
            print("表结构:")
            for col in columns_info:
                print(f"  - {col[1]} ({col[2]})")
            
            # 2. 查询示例记录
            logging.info("查询示例记录")
            sample = conn.execute(text("SELECT * FROM bull_library LIMIT 1")).fetchone()
            if sample:
                print("\n示例记录:")
                for key, value in dict(sample).items():
                    print(f"  - {key}: {value}")
            
            # 3. 测试每个公牛ID
            print("\n测试各个公牛ID:")
            for bull_id in test_bulls:
                print(f"\n测试公牛ID: {bull_id}")
                
                # 3.1 精确匹配NAAB
                query1 = f"SELECT `BULL NAAB`, `BULL REG` FROM bull_library WHERE `BULL NAAB` = '{bull_id}'"
                result1 = conn.execute(text(query1)).fetchall()
                print(f"  NAAB精确匹配: 找到{len(result1)}条记录")
                for row in result1:
                    print(f"    - NAAB: {row['BULL NAAB']}, REG: {row['BULL REG']}")
                
                # 3.2 精确匹配REG
                query2 = f"SELECT `BULL NAAB`, `BULL REG` FROM bull_library WHERE `BULL REG` = '{bull_id}'"
                result2 = conn.execute(text(query2)).fetchall()
                print(f"  REG精确匹配: 找到{len(result2)}条记录")
                for row in result2:
                    print(f"    - NAAB: {row['BULL NAAB']}, REG: {row['BULL REG']}")
                
                # 3.3 模糊匹配
                # 提取数字部分
                number_match = re.search(r'(\d+)$', bull_id)
                if number_match:
                    number_part = number_match.group(1)
                    query3 = f"SELECT `BULL NAAB`, `BULL REG` FROM bull_library WHERE `BULL NAAB` LIKE '%{number_part}%' OR `BULL REG` LIKE '%{number_part}%'"
                    result3 = conn.execute(text(query3)).fetchall()
                    print(f"  数字部分({number_part})模糊匹配: 找到{len(result3)}条记录")
                    for row in result3:
                        print(f"    - NAAB: {row['BULL NAAB']}, REG: {row['BULL REG']}")
                
                # 3.4 尝试不同格式
                # 去掉前缀的0
                if bull_id.startswith('0'):
                    no_leading_zero = bull_id.lstrip('0')
                    query4 = f"SELECT `BULL NAAB`, `BULL REG` FROM bull_library WHERE `BULL NAAB` LIKE '%{no_leading_zero}%' OR `BULL REG` LIKE '%{no_leading_zero}%'"
                    result4 = conn.execute(text(query4)).fetchall()
                    print(f"  去掉前导0({no_leading_zero})模糊匹配: 找到{len(result4)}条记录")
                    for row in result4:
                        print(f"    - NAAB: {row['BULL NAAB']}, REG: {row['BULL REG']}")
                        
                # 3.5 尝试使用REG格式
                # 例如 001HO02452 -> HOFRA006950324340
                query5 = f"""
                    SELECT `BULL NAAB`, `BULL REG` 
                    FROM bull_library 
                    WHERE `BULL NAAB` = '{bull_id}' 
                    OR `BULL REG` = '{bull_id}'
                    OR `BULL NAAB` LIKE '%{bull_id}%' 
                    OR `BULL REG` LIKE '%{bull_id}%'
                """
                result5 = conn.execute(text(query5)).fetchall()
                print(f"  扩展模糊匹配: 找到{len(result5)}条记录")
                for row in result5:
                    print(f"    - NAAB: {row['BULL NAAB']}, REG: {row['BULL REG']}")
    
    except Exception as e:
        logging.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

def test_improved_query():
    """测试改进的查询方法"""
    # 要测试的公牛ID
    test_bulls = ['001HO02452', '001HO02478', '001HO02556', '001HO02623']
    bull_ids = set(test_bulls)
    
    # 连接数据库
    logging.info(f"连接数据库: {LOCAL_DB_PATH}")
    engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}")
    
    try:
        # 将集合转换为列表，方便处理
        bull_ids_list = list(bull_ids)
        print(f"要查询的公牛号: {bull_ids}")
        
        # 构建更灵活的查询条件
        where_conditions = []
        for bull_id in bull_ids_list:
            bull_id_str = str(bull_id).strip()
            # 精确匹配
            where_conditions.append(f"`BULL NAAB` = '{bull_id_str}'")
            where_conditions.append(f"`BULL REG` = '{bull_id_str}'")
            
            # 提取数字部分进行匹配 (适用于格式不完全一致的情况)
            number_match = re.search(r'(\d+)$', bull_id_str)
            if number_match:
                number_part = number_match.group(1)
                if len(number_part) >= 4:  # 只使用足够长的数字部分
                    where_conditions.append(f"`BULL NAAB` LIKE '%{number_part}%'")
                    where_conditions.append(f"`BULL REG` LIKE '%{number_part}%'")
        
        query = f"""
            SELECT `BULL NAAB`, `BULL REG`, 
                HH1, HH2, HH3, HH4, HH5, HH6, 
                BLAD, Chondrodysplasia, Citrullinemia, 
                DUMPS, `Factor XI`, CVM, Brachyspina, 
                Mulefoot, `Cholesterol deficiency Deficiency Carrier` as `Cholesterol deficiency`, MW
            FROM bull_library 
            WHERE {" OR ".join(where_conditions)}
        """
        
        # 执行查询
        with engine.connect() as conn:
            print(f"执行查询...")
            result = conn.execute(text(query)).fetchall()
            print(f"查询到 {len(result)} 条记录")
            
            # 处理查询结果
            found_bulls = set()
            for row in result:
                row_dict = dict(row)  # 转换为普通字典
                naab = row_dict['BULL NAAB']
                reg = row_dict['BULL REG']
                
                print(f"找到匹配: NAAB={naab}, REG={reg}")
                
                # 检查是否匹配我们要找的公牛
                for bull_id in bull_ids_list:
                    bull_id_str = str(bull_id).strip()
                    
                    # 精确匹配
                    if bull_id_str == str(naab) or bull_id_str == str(reg):
                        found_bulls.add(bull_id_str)
                        print(f"  精确匹配: {bull_id_str}")
                        continue
                    
                    # 数字末尾匹配
                    number_match = re.search(r'(\d+)$', bull_id_str)
                    if number_match:
                        number_part = number_match.group(1)
                        if (len(number_part) >= 4 and 
                            (str(naab) and number_part in str(naab) or 
                             str(reg) and number_part in str(reg))):
                            found_bulls.add(bull_id_str)
                            print(f"  数字匹配: {bull_id_str} (数字部分: {number_part})")
                            continue
            
            # 打印未找到的公牛
            missing_bulls = bull_ids - found_bulls
            if missing_bulls:
                print(f"未找到: {missing_bulls}")
            else:
                print("所有公牛都找到了！")
    
    except Exception as e:
        logging.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== 测试基本查询 ===")
    test_bull_query()
    print("\n\n=== 测试改进的查询方法 ===")
    test_improved_query() 