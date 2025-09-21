# core/data/uploader.py

import datetime
import logging
import traceback
import shutil
from pathlib import Path
from core.data.processor import (
    process_breeding_record_file,
    process_cow_data_file,
    process_bull_data_file,
    process_body_conformation_file,
    process_genomic_data_file
)
import pandas as pd

# 设置日志配置（可选）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_and_standardize_breeding_data(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    处理上传的配种记录数据并进行标准化。

    参数:
        input_files (list[Path]): 要上传的配种记录数据文件列表。
        project_path (Path): 当前项目的路径。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的配种记录数据文件路径。
    """
    print("[DEBUG-BREEDING-UPLOAD-1] 开始上传并标准化配种记录数据")
    logging.info("开始上传并标准化配种记录数据")
    
    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

    # 检查是否已经上传母牛数据
    cow_data_file = standardized_path / "processed_cow_data.xlsx"
    if not cow_data_file.exists():
        error_msg = "请先上传并处理母牛数据，再上传配种记录"
        print(f"[DEBUG-BREEDING-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)
    else:
        print(f"[DEBUG-BREEDING-UPLOAD-2] 找到母牛数据文件: {cow_data_file}")
        
    # 读取母牛数据
    try:
        print("[DEBUG-BREEDING-UPLOAD-3] 读取母牛数据...")
        cow_df = pd.read_excel(cow_data_file, dtype={'cow_id': str, 'sire': str})
        print(f"[DEBUG-BREEDING-UPLOAD-4] 母牛数据读取成功，形状: {cow_df.shape}")
    except Exception as e:
        error_msg = f"读取母牛数据时出错: {e}"
        print(f"[DEBUG-BREEDING-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 确保只上传一个文件
    if len(input_files) != 1:
        logging.error("请上传且仅上传一个配种记录数据文件。")
        raise ValueError("请上传且仅上传一个配种记录数据文件。")

    source_file = input_files[0]
    if not source_file.exists():
        logging.error(f"输入文件不存在: {source_file}")
        raise FileNotFoundError(f"输入文件不存在: {source_file}")

    # 固定文件名为 'breeding_records.xlsx'
    target_file = raw_data_path / "breeding_records.xlsx"

    # 检查源文件和目标文件是否相同
    if source_file.resolve() == target_file.resolve():
        logging.info(f"源文件已在目标位置，跳过复制: {target_file}")
    else:
        shutil.copy2(source_file, target_file)
        logging.info(f"已上传并重命名配种记录文件至: {target_file}")
    print(f"[DEBUG-BREEDING-UPLOAD-5] 已上传配种记录文件至: {target_file}")

    # 处理配种记录，传入母牛数据用于父号匹配
    print("[DEBUG-BREEDING-UPLOAD-6] 开始处理配种记录数据...")
    final_path = process_breeding_record_file(
        target_file,
        project_path,
        cow_df=cow_df,  # 传入母牛数据，用于匹配父号
        progress_callback=progress_callback
    )
    
    if final_path is None or not final_path.exists():
        logging.error("标准化后的配种记录数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的配种记录数据文件未生成，请检查标准化逻辑。")

    print(f"[DEBUG-BREEDING-UPLOAD-7] 配种记录数据已标准化并保存至: {final_path}")
    logging.info(f"配种记录数据已标准化并保存至: {final_path}")
    return final_path


def upload_and_standardize_cow_data(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    处理上传的母牛数据并进行标准化，同时自动重新映射配种记录中的父号。

    参数:
        input_files (list[Path]): 要上传的母牛数据文件列表。
        project_path (Path): 当前项目的路径。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的母牛数据文件路径。
    """
    import logging
    print("[DEBUG-UPLOAD-1] 开始上传并标准化母牛数据")
    
    # 配置详细日志记录
    log_file = project_path / "cow_data_upload.log"
    try:
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
        )
        print(f"[DEBUG-UPLOAD-2] 日志文件配置在: {log_file}")
    except Exception as e:
        print(f"[DEBUG-UPLOAD-ERROR] 配置日志文件时出错: {e}")
    
    logging.info("开始上传并标准化母牛数据")
    logging.info(f"项目路径: {project_path}")
    logging.info(f"输入文件列表: {input_files}")
    print(f"[DEBUG-UPLOAD-3] 项目路径: {project_path}")
    print(f"[DEBUG-UPLOAD-4] 输入文件列表: {input_files}")
    
    if not project_path.is_dir():
        error_msg = f"项目路径不存在或无效: {project_path}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 创建必要的目录
    try:
        print("[DEBUG-UPLOAD-5] 开始创建必要目录...")
        raw_data_path = project_path / "raw_data"
        standardized_path = project_path / "standardized_data"
        raw_data_path.mkdir(parents=True, exist_ok=True)
        standardized_path.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG-UPLOAD-6] 创建目录成功: raw_data_path={raw_data_path}, standardized_path={standardized_path}")
        logging.info(f"创建目录成功: raw_data_path={raw_data_path}, standardized_path={standardized_path}")
    except Exception as e:
        error_msg = f"创建目录时出错: {e}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 确保只上传一个文件
    if not input_files:
        error_msg = "未提供输入文件。"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)
        
    if len(input_files) != 1:
        error_msg = f"请上传且仅上传一个母牛数据文件，当前文件数: {len(input_files)}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)

    source_file = input_files[0]
    print(f"[DEBUG-UPLOAD-7] 源文件路径: {source_file}")
    logging.info(f"源文件路径: {source_file}")
    
    if not source_file.exists():
        error_msg = f"输入文件不存在: {source_file}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 记录文件信息
    try:
        print("[DEBUG-UPLOAD-8] 获取文件信息...")
        file_size = source_file.stat().st_size
        print(f"[DEBUG-UPLOAD-9] 源文件大小: {file_size} 字节")
        logging.info(f"源文件大小: {file_size} 字节")
        if file_size == 0:
            error_msg = f"源文件为空: {source_file}"
            print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
            logging.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"获取文件信息时出错: {e}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 固定文件名为 'cow_data.xlsx'
    target_file = raw_data_path / "cow_data.xlsx"

    # 检查源文件和目标文件是否相同
    import os
    if source_file.resolve() == target_file.resolve():
        print(f"[DEBUG-UPLOAD-10] 源文件已在目标位置，跳过复制: {target_file}")
        logging.info(f"源文件已在目标位置，跳过复制: {target_file}")
    else:
        try:
            print(f"[DEBUG-UPLOAD-10] 开始复制文件: {source_file} -> {target_file}")
            import shutil
            shutil.copy2(source_file, target_file)
            print(f"[DEBUG-UPLOAD-11] 已上传并重命名母牛数据文件至: {target_file}")
            logging.info(f"已上传并重命名母牛数据文件至: {target_file}")
        except Exception as e:
            error_msg = f"复制文件时出错: {e}"
            print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
            logging.error(error_msg)
            raise ValueError(error_msg)

    # 处理母牛数据
    try:
        print("[DEBUG-UPLOAD-12] 开始处理母牛数据...")
        if progress_callback:
            progress_callback(10, "开始处理母牛数据...")
        
        final_path = process_cow_data_file(
            target_file,
            project_path,
            progress_callback=progress_callback
        )
        
        print(f"[DEBUG-UPLOAD-13] 处理完成，得到结果路径: {final_path}")
        
        if final_path is None or not final_path.exists():
            error_msg = "标准化后的母牛数据文件未生成，请检查标准化逻辑。"
            print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
            logging.error(error_msg)
            raise ValueError(error_msg)
        
        print(f"[DEBUG-UPLOAD-14] 母牛数据已标准化并保存至: {final_path}")
        logging.info(f"母牛数据已标准化并保存至: {final_path}")
        
        if progress_callback:
            progress_callback(80, "母牛数据处理完成，开始映射配种记录...")
    except Exception as e:
        error_msg = f"处理母牛数据时出错: {e}"
        print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
        logging.error(error_msg)
        import traceback
        print(traceback.format_exc())
        logging.error(traceback.format_exc())
        raise ValueError(error_msg)

    # 检查是否存在标准化后的配种记录文件
    breeding_records_file = standardized_path / "processed_breeding_data.xlsx"
    if breeding_records_file.exists():
        try:
            print("[DEBUG-UPLOAD-15] 开始重新处理配种记录以映射父号")
            logging.info("开始重新处理配种记录以映射父号")
            if progress_callback:
                progress_callback(85, "开始重新映射配种记录中的父号...")
                
            # 读取标准化后的母牛数据
            print("[DEBUG-UPLOAD-16] 读取标准化后的母牛数据...")
            import pandas as pd
            try:
                cow_df = pd.read_excel(final_path, dtype={'cow_id': str, 'sire': str})
                print(f"[DEBUG-UPLOAD-17] 读取成功，数据形状: {cow_df.shape}")
            except Exception as e:
                error_msg = f"读取标准化的母牛数据失败: {e}"
                print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
                logging.error(error_msg)
                # 跳过后续处理，但不抛出异常
                if progress_callback:
                    progress_callback(95, f"重新映射父号时出错: {e}，但继续处理")
                return final_path
            
            # 读取原始配种记录文件
            raw_breeding_records_file = raw_data_path / "breeding_records.xlsx"
            if raw_breeding_records_file.exists():
                print(f"[DEBUG-UPLOAD-18] 找到原始配种记录文件: {raw_breeding_records_file}")
                # 尝试重新处理配种记录，但跳过任何错误
                try:
                    # 安全导入
                    try:
                        from core.data.processor import process_breeding_record_file
                    except ImportError as ie:
                        print(f"[DEBUG-UPLOAD-ERROR] 无法导入process_breeding_record_file: {ie}")
                        if progress_callback:
                            progress_callback(95, "导入配种记录处理函数失败，跳过此步骤")
                        return final_path
                    
                    # 创建安全的进度回调
                    def safe_progress_callback(p):
                        try:
                            if progress_callback:
                                limited_p = min(p, 100)
                                limited_overall = 85 + limited_p // 10
                                message = f"重新映射父号...{limited_p}%"
                                print(f"[DEBUG-UPLOAD-PROGRESS] 映射进度: {limited_p}%, 整体进度: {limited_overall}%")
                                progress_callback(limited_overall, message)
                        except Exception as e:
                            print(f"[DEBUG-UPLOAD-ERROR] 进度回调出错: {e}")
                    
                    # 处理配种记录，但跳过错误
                    try:
                        process_breeding_record_file(
                            raw_breeding_records_file,
                            project_path,
                            cow_df=cow_df,
                            progress_callback=safe_progress_callback
                        )
                        print("[DEBUG-UPLOAD-19] 配种记录中的父号映射已完成")
                    except Exception as e:
                        print(f"[DEBUG-UPLOAD-ERROR] 处理配种记录失败: {e}")
                        import traceback
                        print(traceback.format_exc())
                        # 不抛出异常
                    
                    # 不管成功与否，都标记为完成
                    if progress_callback:
                        progress_callback(95, "配种记录处理完成")
                except Exception as e:
                    error_msg = f"配种记录处理过程中发生未预期错误: {e}"
                    print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
                    import traceback
                    print(traceback.format_exc())
                    # 不抛出异常
                    if progress_callback:
                        progress_callback(95, "配种记录处理过程中发生错误，但继续后续处理")
            else:
                print("[DEBUG-UPLOAD-20] 未找到原始配种记录文件，无法重新映射父号")
                logging.warning("未找到原始配种记录文件，无法重新映射父号")
                if progress_callback:
                    progress_callback(95, "未找到原始配种记录文件，无法重新映射父号")
        except Exception as e:
            error_msg = f"重新映射配种记录父号时发生错误: {e}"
            print(f"[DEBUG-UPLOAD-ERROR] {error_msg}")
            logging.error(error_msg)
            import traceback
            print(traceback.format_exc())
            logging.error(traceback.format_exc())
            # 不抛出异常，继续返回结果
            if progress_callback:
                progress_callback(95, f"重新映射配种记录父号时发生错误，但继续后续处理")
    
    if progress_callback:
        progress_callback(100, "母牛数据处理完成。")
    
    print("[DEBUG-UPLOAD-21] 母牛数据上传和标准化全部完成")
    logging.info("母牛数据上传和标准化全部完成")
    return final_path


def upload_and_standardize_bull_data(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    处理上传的公牛数据并进行标准化。

    参数:
        input_files (list[Path]): 要上传的公牛数据文件列表。
        project_path (Path): 当前项目的路径。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的公牛数据文件路径。
    """
    logging.info("开始上传并标准化公牛数据")
    
    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

    # 确保只上传一个文件
    if len(input_files) != 1:
        logging.error("请上传且仅上传一个公牛数据文件。")
        raise ValueError("请上传且仅上传一个公牛数据文件。")

    source_file = input_files[0]
    if not source_file.exists():
        logging.error(f"输入文件不存在: {source_file}")
        raise FileNotFoundError(f"输入文件不存在: {source_file}")

    # 固定文件名为 'bull_data.xlsx'
    target_file = raw_data_path / "bull_data.xlsx"

    # 检查源文件和目标文件是否相同
    if source_file.resolve() == target_file.resolve():
        logging.info(f"源文件已在目标位置，跳过复制: {target_file}")
    else:
        shutil.copy2(source_file, target_file)
        logging.info(f"已上传并重命名公牛数据文件至: {target_file}")

    # 处理公牛数据
    final_path = process_bull_data_file(
        target_file,
        project_path,
        progress_callback=progress_callback
    )
    if final_path is None or not final_path.exists():
        logging.error("标准化后的公牛数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的公牛数据文件未生成，请检查标准化逻辑。")

    logging.info(f"公牛数据已标准化并保存至: {final_path}")
    return final_path


def upload_and_standardize_body_data(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    处理上传的体型外貌数据并进行标准化。

    参数:
        input_files (list[Path]): 要上传的体型外貌数据文件列表。
        project_path (Path): 当前项目的路径。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的体型外貌数据文件路径。
    """
    logging.info("开始上传并标准化体型外貌数据")
    
    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

    # 确保只上传一个文件
    if len(input_files) != 1:
        logging.error("请上传且仅上传一个体型外貌数据文件。")
        raise ValueError("请上传且仅上传一个体型外貌数据文件。")

    source_file = input_files[0]
    if not source_file.exists():
        logging.error(f"输入文件不存在: {source_file}")
        raise FileNotFoundError(f"输入文件不存在: {source_file}")

    # 固定文件名为 'body_conformation.xlsx'
    target_file = raw_data_path / "body_conformation.xlsx"

    # 检查源文件和目标文件是否相同
    if source_file.resolve() == target_file.resolve():
        logging.info(f"源文件已在目标位置，跳过复制: {target_file}")
    else:
        shutil.copy2(source_file, target_file)
        logging.info(f"已上传并重命名体型外貌数据文件至: {target_file}")

    # 处理体型外貌数据
    final_path = process_body_conformation_file(
        target_file,
        project_path,
        progress_callback=progress_callback
    )
    if final_path is None or not final_path.exists():
        logging.error("标准化后的体型外貌数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的体型外貌数据文件未生成，请检查标准化逻辑。")

    logging.info(f"体型外貌数据已标准化并保存至: {final_path}")
    return final_path

def upload_and_standardize_genomic_data(input_files: list[Path], project_path: Path, progress_callback=None) -> Path:
    """
    处理上传的基因组检测数据并进行标准化。

    参数:
        input_files (list[Path]): 要上传的基因组检测数据文件列表。
        project_path (Path): 当前项目的路径。
        progress_callback (callable, optional): 进度回调函数，用于更新进度条或显示信息。

    返回:
        Path: 标准化后的基因组检测数据文件路径。
    """
    logging.info("开始上传并标准化基因组检测数据")

    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data" / "genomic_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

    # 为每个上传的文件添加序号并保存到 raw_data
    renamed_files = []
    for idx, source_file in enumerate(input_files, start=1):
        if not source_file.exists():
            logging.error(f"输入文件不存在: {source_file}")
            raise FileNotFoundError(f"输入文件不存在: {source_file}")

        # 创建带有序号的文件名，例如 genomic_data_1.xlsx
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        target_file = raw_data_path / f"genomic_data_{timestamp}_{idx}{source_file.suffix}"

        # 检查源文件和目标文件是否相同
        if source_file.resolve() == target_file.resolve():
            logging.info(f"源文件已在目标位置，跳过复制: {target_file}")
        else:
            shutil.copy2(source_file, target_file)
            logging.info(f"已上传并重命名基因组检测数据文件至: {target_file}")
        renamed_files.append(target_file)

    # 创建一个包装函数来同时处理进度和消息
    def progress_wrapper(progress_value, message=None):
        if progress_callback:
            try:
                # 尝试传递两个参数
                progress_callback(progress_value, message)
            except TypeError:
                # 如果失败，只传递进度值（向后兼容）
                if progress_value is not None:
                    progress_callback(progress_value)

    # 处理基因组检测数据
    final_path = process_genomic_data_file(
        renamed_files,
        project_path,
        progress_callback=progress_wrapper
    )
    if final_path is None or not final_path.exists():
        logging.error("标准化后的基因组检测数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的基因组检测数据文件未生成，请检查标准化逻辑。")

    logging.info(f"基因组检测数据已标准化并保存至: {final_path}")
    return final_path