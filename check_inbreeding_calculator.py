import sqlite3
import pandas as pd
from pathlib import Path
import time
import sys

class SimpleInbreedingCalculator:
    """简化版的系谱计算器，用于检测递归问题"""
    
    def __init__(self, db_path, cow_data_path=None):
        """初始化计算器"""
        self.db_path = db_path
        self.cow_data = None
        self.max_depth = 5  # 限制递归深度
        self.processed_ids = set()  # 用于检测循环引用
        
        if cow_data_path:
            try:
                self.cow_data = pd.read_excel(cow_data_path)
                print(f"成功加载母牛数据，共{len(self.cow_data)}行")
            except Exception as e:
                print(f"加载母牛数据失败: {e}")
    
    def get_bull_info(self, bull_id):
        """获取公牛信息"""
        if not bull_id or pd.isna(bull_id) or bull_id == '':
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT `BULL NAAB` as naab, `BULL REG` as reg, 
                       `SIRE REG` as sire_reg, `MGS REG` as mgs_reg,
                       GIB as gib
                FROM bull_library 
                WHERE `BULL NAAB` = ? OR `BULL REG` = ?
            """
            
            result = pd.read_sql_query(query, conn, params=[bull_id, bull_id])
            conn.close()
            
            if len(result) > 0:
                return result.iloc[0].to_dict()
            return None
        except Exception as e:
            print(f"查询公牛信息时出错: {e}")
            return None
    
    def get_cow_info(self, cow_id):
        """获取母牛信息"""
        if self.cow_data is None or not cow_id:
            return None
            
        # 查找cow_id列
        cow_id_col = None
        for col in ['cow_id', '母牛号', '耳号']:
            if col in self.cow_data.columns:
                cow_id_col = col
                break
                
        if cow_id_col is None:
            print("无法找到母牛ID列")
            return None
            
        # 查找匹配的行
        matches = self.cow_data[self.cow_data[cow_id_col] == cow_id]
        if len(matches) == 0:
            return None
            
        # 查找sire列
        sire_col = None
        for col in ['sire', '父号']:
            if col in self.cow_data.columns:
                sire_col = col
                break
                
        if sire_col is None:
            print("无法找到父号列")
            return None
            
        result = {
            'id': cow_id,
            'sire': str(matches.iloc[0][sire_col]) if pd.notna(matches.iloc[0][sire_col]) else None
        }
        
        return result
    
    def build_complete_pedigree(self, animal_id, depth=0):
        """构建完整系谱，带有循环检测和深度限制"""
        if animal_id in self.processed_ids:
            print(f"检测到循环引用: {animal_id}，跳过")
            return {'id': animal_id, 'cycle_detected': True}
            
        if depth >= self.max_depth:
            print(f"达到最大递归深度 {self.max_depth}，对ID {animal_id} 停止展开")
            return {'id': animal_id, 'max_depth_reached': True}
            
        self.processed_ids.add(animal_id)
        
        # 首先尝试作为公牛
        animal_info = self.get_bull_info(animal_id)
        
        if animal_info:
            result = {'id': animal_id, 'reg': animal_info.get('reg')}
            
            # 递归获取父系信息
            sire_reg = animal_info.get('sire_reg')
            if sire_reg and sire_reg != '':
                print(f"深度 {depth}: 展开父系 {sire_reg}")
                result['sire'] = self.build_complete_pedigree(sire_reg, depth + 1)
            
            # 递归获取母系信息
            mgs_reg = animal_info.get('mgs_reg')
            if mgs_reg and mgs_reg != '':
                print(f"深度 {depth}: 展开母系父亲 {mgs_reg}")
                # 这里不再展开整个母系，只获取母系的父亲信息
                result['mgs'] = {'id': mgs_reg}
            
            self.processed_ids.remove(animal_id)  # 处理完移除
            return result
        
        # 然后尝试作为母牛
        animal_info = self.get_cow_info(animal_id)
        
        if animal_info:
            result = {'id': animal_id}
            
            # 递归获取父系信息
            sire = animal_info.get('sire')
            if sire and sire != '':
                print(f"深度 {depth}: 展开父系 {sire}")
                result['sire'] = self.build_complete_pedigree(sire, depth + 1)
            
            self.processed_ids.remove(animal_id)  # 处理完移除
            return result
        
        # 如果找不到信息
        self.processed_ids.remove(animal_id)  # 处理完移除
        return {'id': animal_id, 'not_found': True}
    
    def test_pedigree_building(self, test_ids):
        """测试系谱构建功能"""
        for animal_id in test_ids:
            print(f"\n===== 测试ID: {animal_id} =====")
            start_time = time.time()
            try:
                # 每次测试前重置处理过的ID集合
                self.processed_ids = set()
                pedigree = self.build_complete_pedigree(animal_id)
                elapsed_time = time.time() - start_time
                print(f"构建用时: {elapsed_time:.2f}秒")
                print(f"系谱摘要: {self._summarize_pedigree(pedigree)}")
            except Exception as e:
                elapsed_time = time.time() - start_time
                print(f"系谱构建失败: {e}, 用时: {elapsed_time:.2f}秒")
    
    def _summarize_pedigree(self, pedigree, prefix=''):
        """生成系谱摘要，避免打印完整系谱"""
        if not pedigree:
            return "None"
            
        result = []
        result.append(f"{prefix}ID: {pedigree.get('id')}")
        
        if 'cycle_detected' in pedigree:
            result.append(f"{prefix}[循环引用]")
            return ", ".join(result)
            
        if 'max_depth_reached' in pedigree:
            result.append(f"{prefix}[达到最大深度]")
            return ", ".join(result)
            
        if 'not_found' in pedigree:
            result.append(f"{prefix}[未找到记录]")
            return ", ".join(result)
            
        if 'sire' in pedigree:
            result.append(f"{prefix}父: {pedigree['sire'].get('id')}")
        
        if 'mgs' in pedigree:
            result.append(f"{prefix}母父: {pedigree['mgs'].get('id')}")
            
        return ", ".join(result)

# 主函数
def main():
    db_path = "/Users/Shared/Files From d.localized/projects/mating/genetic_improve/local_bull_library.db"
    
    # 首先测试一下数据库连接
    print("测试数据库连接...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bull_library")
        count = cursor.fetchone()[0]
        print(f"bull_library表中有 {count} 条记录")
        conn.close()
    except Exception as e:
        print(f"连接数据库失败: {e}")
        sys.exit(1)
    
    # 找出样本项目中的cow_data文件
    print("\n查找样本项目中的cow_data文件...")
    base_path = Path("/Users/Shared/Files From d.localized/projects/mating/genetic_improve")
    project_paths = list(base_path.glob("genetic_projects/**/standardized_data/processed_cow_data.xlsx"))
    
    if not project_paths:
        print("未找到任何cow_data文件")
        sys.exit(1)
        
    cow_data_path = project_paths[0]
    print(f"使用cow_data文件: {cow_data_path}")
    
    # 初始化计算器
    calculator = SimpleInbreedingCalculator(db_path, cow_data_path)
    
    # 从样例数据中读取一些公牛ID
    print("\n从样例数据中读取一些牛ID...")
    cow_ids = []
    bull_ids = []
    
    try:
        cow_df = pd.read_excel(cow_data_path)
        # 查找cow_id列
        cow_id_col = None
        for col in ['cow_id', '母牛号', '耳号']:
            if col in cow_df.columns:
                cow_id_col = col
                break
                
        if cow_id_col:
            cow_ids = cow_df[cow_id_col].dropna().astype(str).unique()[:5].tolist()
            print(f"获取了 {len(cow_ids)} 个母牛ID样本: {cow_ids}")
        
        # 查找sire列获取公牛ID
        sire_col = None
        for col in ['sire', '父号']:
            if col in cow_df.columns:
                sire_col = col
                break
                
        if sire_col:
            bull_ids = cow_df[sire_col].dropna().astype(str).unique()[:5].tolist()
            print(f"获取了 {len(bull_ids)} 个公牛ID样本: {bull_ids}")
            
    except Exception as e:
        print(f"读取样例数据失败: {e}")
    
    # 补充一些公牛ID
    sample_bull_ids = ['001HO09162', '007HO16385', '001HO09154', '001HO09174', 
                       '151HO04449', '151HO04311', '007HO16443', '007HO16284']
    
    test_ids = cow_ids + bull_ids + sample_bull_ids
    test_ids = list(set(test_ids))[:10]  # 去重并限制测试数量
    
    # 测试系谱构建
    print("\n开始测试系谱构建...")
    calculator.test_pedigree_building(test_ids)

if __name__ == "__main__":
    main() 