import sys
import pandas as pd
from pathlib import Path
import logging
import traceback

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='test_naab_format.log',
    filemode='w'
)

# 导入需要测试的函数
try:
    from core.data.processor import format_naab_number
    logging.info("成功导入 format_naab_number 函数")
except ImportError as e:
    logging.error(f"导入错误: {e}")
    print(f"导入错误: {e}")
    print("请确保在正确的目录中运行此脚本")
    sys.exit(1)

def test_naab_format():
    """测试 format_naab_number 函数"""
    logging.info("开始测试 format_naab_number 函数")
    
    # 测试用例
    test_cases = [
        ('123HO12345', '123HO12345', False),  # 正确格式
        ('123ho12345', '123HO12345', False),  # 小写字母
        ('123 HO 12345', '123HO12345', False),  # 包含空格
        ('0123HO12345', '123HO12345', False),  # 前导零
        ('123H12345', '123HO12345', False),    # 单字母品种代码
        ('123JE12345', '123JE12345', False),   # 双字母品种代码
        ('123M12345', '123MO12345', False),    # 其他单字母映射
        ('123HO123456', None, True),          # 后缀数字过长
        ('1234HO12345', None, True),          # 站号过长
        ('123X12345', None, True),            # 未知单字母品种代码
        ('123XY12345', None, True),           # 未知双字母品种代码
        ('hello', None, True),                # 完全错误的格式
        ('', None, True),                      # 空字符串
        ('123', None, True),                   # 没有品种代码
        ('HO12345', None, True),               # 没有站号
        ('123HO', None, True),                 # 没有后缀数字
    ]
    
    print("开始测试 format_naab_number 函数")
    print("格式: 原始值 -> 格式化结果 (是否有错误)")
    print("-" * 50)
    
    success_count = 0
    fail_count = 0
    
    for original, expected, should_error in test_cases:
        try:
            formatted, errors = format_naab_number(original)
            has_error = len(errors) > 0
            
            # 检查结果是否符合预期
            if has_error == should_error and (not should_error or formatted == expected):
                result = "通过"
                success_count += 1
            else:
                result = "失败"
                fail_count += 1
                logging.error(f"测试失败: {original} -> {formatted}, 错误: {errors}, 预期: {expected}, 预期错误: {should_error}")
            
            # 打印结果
            print(f"{original} -> {formatted} (错误: {has_error}) - {result}")
            if has_error:
                print(f"  错误信息: {errors}")
                
        except Exception as e:
            print(f"{original} -> 异常: {e} - 失败")
            logging.error(f"处理 {original} 时发生异常: {e}")
            logging.error(traceback.format_exc())
            fail_count += 1
    
    print("-" * 50)
    print(f"测试完成: {success_count} 个通过, {fail_count} 个失败")
    
    # 额外测试: 从excel数据文件中读取更多样例
    print("\n是否要从Excel文件中读取更多测试数据? (Y/N): ", end="")
    answer = input().strip().upper()
    
    if answer == 'Y':
        test_from_file()
    
    logging.info(f"测试完成: {success_count} 个通过, {fail_count} 个失败")
    return success_count, fail_count

def test_from_file():
    """从Excel文件中读取测试数据"""
    file_path = input("请输入Excel文件路径: ")
    
    try:
        # 读取Excel文件
        df = pd.read_excel(file_path)
        logging.info(f"成功读取文件 {file_path}, 形状: {df.shape}")
        print(f"成功读取文件, 共 {df.shape[0]} 行数据")
        
        # 查找可能包含NAAB号的列
        potential_columns = []
        for column in df.columns:
            col_name = str(column).lower()
            if any(keyword in col_name for keyword in ['sire', 'bull', '父亲', '公牛', '外祖父', 'naab']):
                potential_columns.append(column)
        
        if not potential_columns:
            print("未找到可能包含NAAB号的列，将检查所有列")
            potential_columns = df.columns.tolist()
        
        print(f"将检查以下列: {potential_columns}")
        
        for column in potential_columns:
            print(f"\n测试列: {column}")
            print("-" * 50)
            
            success = 0
            fail = 0
            
            # 先检查数据类型并转换为字符串
            df[column] = df[column].astype(str)
            
            # 获取唯一值
            unique_values = df[column].unique()
            print(f"共 {len(unique_values)} 个唯一值")
            
            # 测试前10个值
            for i, value in enumerate(unique_values[:10]):
                try:
                    if value == 'nan' or value == '' or value.isspace():
                        continue
                        
                    formatted, errors = format_naab_number(value)
                    has_error = len(errors) > 0
                    
                    print(f"{value} -> {formatted} (错误: {has_error})")
                    if has_error:
                        print(f"  错误信息: {errors}")
                        fail += 1
                    else:
                        success += 1
                        
                except Exception as e:
                    print(f"{value} -> 异常: {e}")
                    logging.error(f"处理 {value} 时发生异常: {e}")
                    fail += 1
            
            print(f"列 {column} 测试结果: {success} 个成功, {fail} 个失败")
        
    except Exception as e:
        print(f"处理文件时出错: {e}")
        logging.error(f"处理文件时出错: {e}")
        logging.error(traceback.format_exc())

if __name__ == "__main__":
    print("NAAB格式化函数测试工具")
    test_naab_format()
    print("\n测试完成! 请查看 test_naab_format.log 获取详细日志。") 