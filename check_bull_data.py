import sqlite3
import pandas as pd

def check_bull_data():
    """检查bull_library表数据，特别关注SQL查询问题"""
    try:
        # 连接数据库
        conn = sqlite3.connect("local_bull_library.db")
        
        # 首先检查列名
        query = "PRAGMA table_info(bull_library)"
        columns_info = pd.read_sql_query(query, conn)
        print("表bull_library的列信息:")
        print(columns_info[['name', 'type']])
        
        # 统计表中的记录数
        query = "SELECT COUNT(*) FROM bull_library"
        count = pd.read_sql_query(query, conn).iloc[0, 0]
        print(f"\n表bull_library中共有 {count} 条记录")
        
        # 检查示例公牛ID
        sample_ids = ['001HO09162', '007HO16385', '001HO09154', '001HO09174', 
                      '151HO04449', '151HO04311', '007HO16443', '007HO16284']
        
        print("\n尝试使用IN查询样本公牛号:")
        # 尝试使用IN语句
        placeholders = ','.join(['?'] * len(sample_ids))
        query = f"""
            SELECT `BULL NAAB`, `BULL REG`, 
                HH1, HH2, HH3, HH4, HH5, HH6, 
                BLAD, Chondrodysplasia, Citrullinemia, 
                DUMPS, `Factor XI`, CVM, Brachyspina, 
                Mulefoot, `Cholesterol deficiency Deficiency Carrier` as `Cholesterol deficiency`, MW
            FROM bull_library 
            WHERE `BULL NAAB` IN ({placeholders}) 
            OR `BULL REG` IN ({placeholders})
        """
        
        # 打印完整的SQL
        print(f"SQL查询: {query}")
        print(f"参数: {sample_ids + sample_ids}")
        
        # 执行查询
        params = sample_ids + sample_ids  # 每个ID用于NAAB和REG两个字段
        result = pd.read_sql_query(query, conn, params=params)
        print(f"\n查询结果: {len(result)} 行")
        
        if len(result) > 0:
            print("\n查询结果前几行:")
            print(result.head())
        else:
            # 检查是否有任何ID存在
            for bull_id in sample_ids:
                query = f"""
                    SELECT `BULL NAAB`, `BULL REG` 
                    FROM bull_library 
                    WHERE `BULL NAAB` = ? OR `BULL REG` = ?
                """
                result = pd.read_sql_query(query, conn, params=[bull_id, bull_id])
                if len(result) > 0:
                    print(f"ID {bull_id} 存在于数据库中: {result.iloc[0].to_dict()}")
        
        # 检查表示例数据
        print("\n表bull_library随机10行:")
        query = "SELECT `BULL NAAB`, `BULL REG` FROM bull_library ORDER BY RANDOM() LIMIT 10"
        random_samples = pd.read_sql_query(query, conn)
        print(random_samples)
        
        # 检查Factor XI列
        print("\n检查 'Factor XI' 列的唯一值:")
        query = "SELECT DISTINCT `Factor XI` FROM bull_library"
        factor_values = pd.read_sql_query(query, conn)
        print(factor_values)

        # 检查代码中使用的基因列
        gene_columns = [
            'HH1', 'HH2', 'HH3', 'HH4', 'HH5', 'HH6', 
            'BLAD', 'Chondrodysplasia', 'Citrullinemia', 
            'DUMPS', 'Factor XI', 'CVM', 'Brachyspina', 
            'Mulefoot', 'Cholesterol deficiency Deficiency Carrier', 'MW'
        ]
        
        print("\n检查基因列的非空值计数:")
        for col in gene_columns:
            query = f'SELECT COUNT(*) FROM bull_library WHERE "{col}" IS NOT NULL AND "{col}" != ""'
            try:
                count = pd.read_sql_query(query, conn).iloc[0, 0]
                print(f"  {col}: {count}")
            except Exception as e:
                print(f"  {col}: 查询出错 - {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"检查数据库时出错: {e}")

if __name__ == "__main__":
    check_bull_data() 