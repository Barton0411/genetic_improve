# core/data/uploader.py

from pathlib import Path
import shutil
from core.data.processor import (
    process_breeding_record_file,
    process_cow_data_file,
    process_bull_data_file,
    process_body_conformation_file
)
import pandas as pd
import logging

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
    logging.info("开始上传并标准化配种记录数据")
    
    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

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
    shutil.copy2(source_file, target_file)
    logging.info(f"已上传并重命名配种记录文件至: {target_file}")

    # 处理配种记录
    final_path = process_breeding_record_file(
        target_file,
        project_path,
        cow_df=None,  # 目前未提供母牛数据，父号列将为空
        progress_callback=progress_callback
    )
    if final_path is None or not final_path.exists():
        logging.error("标准化后的配种记录数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的配种记录数据文件未生成，请检查标准化逻辑。")

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
    logging.info("开始上传并标准化母牛数据")
    
    if not project_path.is_dir():
        logging.error(f"项目路径不存在或无效: {project_path}")
        raise ValueError(f"项目路径不存在或无效: {project_path}")

    raw_data_path = project_path / "raw_data"
    standardized_path = project_path / "standardized_data"
    raw_data_path.mkdir(parents=True, exist_ok=True)
    standardized_path.mkdir(parents=True, exist_ok=True)

    # 确保只上传一个文件
    if len(input_files) != 1:
        logging.error("请上传且仅上传一个母牛数据文件。")
        raise ValueError("请上传且仅上传一个母牛数据文件。")

    source_file = input_files[0]
    if not source_file.exists():
        logging.error(f"输入文件不存在: {source_file}")
        raise FileNotFoundError(f"输入文件不存在: {source_file}")

    # 固定文件名为 'cow_data.xlsx'
    target_file = raw_data_path / "cow_data.xlsx"
    shutil.copy2(source_file, target_file)
    logging.info(f"已上传并重命名母牛数据文件至: {target_file}")

    # 处理母牛数据
    final_path = process_cow_data_file(
        target_file,
        project_path,
        progress_callback=progress_callback
    )
    if final_path is None or not final_path.exists():
        logging.error("标准化后的母牛数据文件未生成，请检查标准化逻辑。")
        raise ValueError("标准化后的母牛数据文件未生成，请检查标准化逻辑。")

    logging.info(f"母牛数据已标准化并保存至: {final_path}")

    # 自动重新处理配种记录以映射父号
    raw_breeding_records_file = raw_data_path / "breeding_records.xlsx"
    if raw_breeding_records_file.exists():
        try:
            logging.info("开始重新处理配种记录以映射父号")
            # 读取标准化后的母牛数据
            cow_df = pd.read_excel(final_path, dtype={'cow_id': str, 'sire': str})
            logging.info("已读取标准化后的母牛数据")
            # 重新处理配种记录
            process_breeding_record_file(
                raw_breeding_records_file,
                project_path,
                cow_df=cow_df,  # 传递 cow_df
                progress_callback=progress_callback
            )
            if progress_callback:
                progress_callback("配种记录中的父号映射已完成。")
            logging.info("配种记录中的父号映射已完成")
        except Exception as e:
            logging.error(f"重新映射配种记录父号时发生错误: {e}")
            if progress_callback:
                progress_callback(f"重新映射配种记录父号时发生错误: {e}")
            # 可以选择是否抛出异常或记录日志
            pass
    else:
        logging.warning(f"{raw_breeding_records_file} 文件不存在，无法重新映射父号")

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
