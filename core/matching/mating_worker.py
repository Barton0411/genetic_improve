"""
选配工作线程
在后台执行耗时的选配计算
"""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import logging
import traceback

from core.matching.complete_mating_executor import CompleteMatingExecutor

logger = logging.getLogger(__name__)


class MatingWorker(QThread):
    """选配工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # 消息, 进度百分比
    finished = pyqtSignal(dict)  # 结果
    error_occurred = pyqtSignal(str)  # 错误信息
    
    def __init__(self, project_path: Path, params: dict):
        """
        初始化工作线程
        
        Args:
            project_path: 项目路径
            params: 选配参数，包含:
                - bull_inventory: 公牛库存
                - inbreeding_threshold: 近交系数阈值
                - control_defect_genes: 是否控制隐性基因
                - heifer_age_days: 后备牛年龄
                - cycle_days: 周期天数
                - skip_missing_bulls: 是否跳过缺失数据的公牛
        """
        super().__init__()
        self.project_path = project_path
        self.params = params
        self._is_cancelled = False
        
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
        
    def run(self):
        """执行选配任务"""
        try:
            # 创建执行器
            executor = CompleteMatingExecutor(self.project_path)
            
            # 定义进度回调
            def progress_callback(msg, pct):
                if not self._is_cancelled:
                    self.progress_updated.emit(msg, pct)
            
            # 执行选配
            result = executor.execute(
                bull_inventory=self.params.get('bull_inventory', {}),
                inbreeding_threshold=self.params.get('inbreeding_threshold', 0.0625),
                control_defect_genes=self.params.get('control_defect_genes', False),
                heifer_age_days=self.params.get('heifer_age_days', 420),
                cycle_days=self.params.get('cycle_days', 21),
                skip_missing_bulls=self.params.get('skip_missing_bulls', False),
                progress_callback=progress_callback
            )
            
            if not self._is_cancelled:
                self.finished.emit(result)
                
        except Exception as e:
            error_msg = f"选配执行失败: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            if not self._is_cancelled:
                self.error_occurred.emit(str(e))
