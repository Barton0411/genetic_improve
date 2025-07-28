import sqlite3
import sys

def query_database(db_path):
    """查询数据库结构和内容"""
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("数据库中的表:")
        for table in tables:
            print(f"- {table[0]}")
            
        # 对每个表查询结构
        for table in tables:
            table_name = table[0]
            print(f"\n表 '{table_name}' 的结构:")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            for column in columns:
                print(f"  - {column[1]} ({column[2]})")
            
            # 获取表中的行数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  总行数: {count}")
            
            # 如果是bull_library表，显示前3行
            if table_name == 'bull_library':
                print(f"\n表 '{table_name}' 的前3行:")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                rows = cursor.fetchall()
                
                # 获取列名
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]
                
                for row in rows:
                    for i, value in enumerate(row):
                        print(f"  {columns[i]}: {value}")
                    print("")
        
        # 关闭连接
        conn.close()
        
    except Exception as e:
        print(f"查询数据库时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    query_database("local_bull_library.db") 