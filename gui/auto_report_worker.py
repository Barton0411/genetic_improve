"""
自动报告生成工作线程

在后台执行完整流程：数据下载 → 标准化 → 7项数据分析 → Excel报告 → PPT报告
"""

import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class AutoReportWorker(QThread):
    """自动报告生成工作线程"""

    progress = pyqtSignal(int, str)    # (百分比, 消息)
    finished = pyqtSignal(dict)         # 完成结果字典
    error = pyqtSignal(str)             # 错误消息

    # 并行子任务进度信号
    sub_task_progress = pyqtSignal(str, int)   # (task_id, 子任务百分比 0-100)
    sub_task_done = pyqtSignal(str, bool)       # (task_id, 是否成功)
    parallel_start = pyqtSignal(list)           # 并行任务名称列表
    parallel_end = pyqtSignal()                 # 并行阶段结束

    def __init__(self, api_client, farms, project_path, is_merged=False, service_staff=None):
        """
        初始化

        Args:
            api_client: YQN API客户端
            farms: 牧场列表 [{"code": ..., "name": ..., "cow_count": ...}, ...]
            project_path: 项目路径
            is_merged: 是否为合并模式
            service_staff: 服务人员姓名（登录用户）
        """
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = Path(project_path)
        self.is_merged = is_merged
        self.service_staff = service_staff

        # 各步骤结果跟踪
        self.results = {
            'success_items': [],   # 成功的步骤
            'failed_items': [],    # 失败的步骤 [(步骤名, 错误信息)]
            'excel_path': None,    # Excel报告路径
            'ppt_path': None,      # PPT报告路径
        }

    def _make_sub_progress(self, task_name, start_pct, end_pct):
        """创建子任务进度回调，将 0-100% 映射到全局 start_pct-end_pct"""
        def callback(sub_pct, msg=""):
            global_pct = start_pct + int(sub_pct / 100 * (end_pct - start_pct))
            self.progress.emit(global_pct, f"[{task_name}] {msg}")
            # 同时发送子任务独立进度
            try:
                self.sub_task_progress.emit(task_name, int(sub_pct))
            except Exception:
                pass
        return callback

    def run(self):
        """执行完整流程"""
        try:
            # ===== Phase 1: 数据下载与标准化 (0-30%) =====
            self._phase_download_and_standardize()

            # ===== Phase 2: 数据分析 (30-75%) =====
            self._phase_analysis()

            # ===== Phase 3: Excel报告 (75-90%) =====
            self._phase_excel_report()

            # ===== Phase 4: PPT报告 (90-100%) =====
            self._phase_ppt_report()

            self.progress.emit(100, "全部完成!")
            self.finished.emit(self.results)

        except Exception as e:
            logger.exception("自动报告生成失败")
            self.error.emit(f"自动报告生成失败: {str(e)}")

    def _phase_download_and_standardize(self):
        """Phase 1: 数据下载与标准化 (0-30%)"""
        from core.data.yqn_data_converter import YQNDataConverter
        from core.data.uploader import upload_and_standardize_cow_data

        total_farms = len(self.farms)
        all_api_data = []

        # 下载牛群数据 (0-5%)
        for i, farm in enumerate(self.farms):
            farm_code = farm['code']
            farm_name = farm['name']
            pct = int((i / total_farms) * 5)
            self.progress.emit(pct, f"正在下载 {farm_name} 数据...")

            api_data = self.api_client.get_farm_herd(farm_code)
            cow_count = len(api_data.get('data', []))
            farm['cow_count'] = cow_count
            all_api_data.append((farm_code, api_data))

        # 合并+转换 (5-6%)
        self.progress.emit(5, "正在合并数据...")
        if self.is_merged:
            merged_data = YQNDataConverter.merge_herd_data(all_api_data)
        else:
            merged_data = all_api_data[0][1]

        raw_data_dir = self.project_path / "raw_data"
        raw_data_dir.mkdir(parents=True, exist_ok=True)
        excel_path = raw_data_dir / "cow_data.xlsx"
        YQNDataConverter.convert_herd_to_excel(merged_data, excel_path)
        self.progress.emit(6, "数据转换完成")

        # 下载配种记录 (6-10%)
        self.progress.emit(6, "正在下载配种记录...")
        try:
            all_breeding_data = []
            for i, farm in enumerate(self.farms):
                farm_code = farm['code']
                farm_name = farm['name']
                pct = int(6 + (i / total_farms) * 4)
                self.progress.emit(pct, f"正在下载 {farm_name} 配种记录...")
                breeding_data = self.api_client.get_breeding_records(farm_code)
                all_breeding_data.append((farm_code, breeding_data))

            # 转换配种记录 (10-11%)
            self.progress.emit(10, "正在转换配种记录...")
            merged_breeding = YQNDataConverter.merge_breeding_records(all_breeding_data)

            if merged_breeding:
                merged_breeding_api = {"data": {"rows": merged_breeding}}
                breeding_excel_path = raw_data_dir / "breeding_records.xlsx"
                YQNDataConverter.convert_breeding_records_to_excel(
                    merged_breeding_api, breeding_excel_path
                )
            self.progress.emit(11, "配种记录转换完成")
        except Exception as e:
            logger.warning(f"配种记录下载失败（不影响主流程）: {e}")

        # 标准化牛群数据 (11-22%)
        self.progress.emit(11, "正在标准化牛群数据...")

        def standardize_progress(*args):
            if len(args) == 2:
                pct, msg = args
            elif len(args) == 1:
                pct = args[0]
                msg = f"{pct}%"
            else:
                return
            try:
                mapped_pct = 11 + int(pct / 100 * 11)
                self.progress.emit(mapped_pct, f"标准化牛群: {msg}")
            except Exception:
                pass

        upload_and_standardize_cow_data(
            input_files=[excel_path],
            project_path=self.project_path,
            progress_callback=standardize_progress,
            source_system="伊起牛"
        )

        # 标准化配种记录 (22-25%)
        breeding_excel = self.project_path / "raw_data" / "breeding_records.xlsx"
        if breeding_excel.exists():
            self.progress.emit(22, "正在标准化配种记录...")

            def breeding_std_progress(*args):
                if len(args) == 2:
                    pct, msg = args
                elif len(args) == 1:
                    pct = args[0]
                    msg = f"{pct}%"
                else:
                    return
                try:
                    mapped_pct = 22 + int(pct / 100 * 3)
                    self.progress.emit(mapped_pct, f"标准化配种记录: {msg}")
                except Exception:
                    pass

            try:
                from core.data.uploader import upload_and_standardize_breeding_data
                upload_and_standardize_breeding_data(
                    input_files=[breeding_excel],
                    project_path=self.project_path,
                    progress_callback=breeding_std_progress,
                    source_system="伊起牛"
                )
            except Exception as e:
                logger.warning(f"配种记录标准化失败: {e}")

        # 下载冻精库存 (25-26%)
        self.progress.emit(25, "正在下载冻精库存...")
        try:
            all_stock_records = []
            for farm in self.farms:
                farm_code = farm['code']
                stock_data = self.api_client.get_stock_detail(farm_code)
                stock_records = stock_data.get("data", [])
                all_stock_records.extend(stock_records)

            if all_stock_records:
                merged_stock_data = {"code": 200, "data": all_stock_records}
                semen_inventory_path = raw_data_dir / "semen_inventory.xlsx"
                YQNDataConverter.convert_stock_to_semen_inventory(
                    merged_stock_data, semen_inventory_path
                )
                # 标准化冻精库存 (26-30%)
                self.progress.emit(26, "正在标准化冻精库存...")

                def bull_std_progress(*args):
                    if len(args) == 2:
                        pct, msg = args
                    elif len(args) == 1:
                        pct = args[0]
                        msg = f"{pct}%"
                    else:
                        return
                    try:
                        mapped_pct = 26 + int(pct / 100 * 4)
                        self.progress.emit(mapped_pct, f"标准化冻精库存: {msg}")
                    except Exception:
                        pass

                from core.data.uploader import upload_and_standardize_bull_data
                upload_and_standardize_bull_data(
                    input_files=[semen_inventory_path],
                    project_path=self.project_path,
                    progress_callback=bull_std_progress
                )
        except Exception as e:
            logger.warning(f"冻精库存处理失败: {e}")

        self.results['success_items'].append("数据下载与标准化")
        self.progress.emit(30, "数据下载与标准化完成")

    def _phase_analysis(self):
        """Phase 2: 数据分析 (30-75%)

        优化：将原来3轮串行改为2轮。
        唯一真实依赖：cow_index 需要 cow_traits 输出，其余6个任务完全独立。

        第1轮 (30-65%): 6个独立任务并行
          cow_traits, bull_traits, mated_bull_traits, bull_index,
          inbreeding_mated, inbreeding_candidate
        第2轮 (65-75%): cow_index (依赖 cow_traits)
        """
        from core.auto_analysis_runner import (
            run_cow_traits, run_bull_traits, run_mated_bull_traits,
            run_cow_index, run_bull_index, run_inbreeding_analysis
        )

        project = str(self.project_path)

        # --- 第1轮: 6个独立任务并行 (30-65%) ---
        self.progress.emit(30, "开始数据分析（6项并行）...")

        # 任务显示名称映射（子进度回调名 → 显示名）
        task_display_names = [
            "母牛性状分析", "备选公牛性状分析", "已配公牛性状分析",
            "公牛指数排名", "已配公牛近交分析", "备选公牛近交分析"
        ]
        self.parallel_start.emit(task_display_names)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(run_inbreeding_analysis, project, "candidate",
                                self._make_sub_progress("备选公牛近交分析", 54, 65)): "备选公牛近交分析",
                executor.submit(run_inbreeding_analysis, project, "mated",
                                self._make_sub_progress("已配公牛近交分析", 48, 54)): "已配公牛近交分析",
                executor.submit(run_cow_traits, project, None,
                                self._make_sub_progress("母牛性状分析", 30, 35)): "母牛性状分析",
                executor.submit(run_bull_traits, project, None,
                                self._make_sub_progress("备选公牛性状分析", 35, 40)): "备选公牛性状分析",
                executor.submit(run_mated_bull_traits, project, None,
                                self._make_sub_progress("已配公牛性状分析", 40, 44)): "已配公牛性状分析",
                executor.submit(run_bull_index, project, None,
                                self._make_sub_progress("公牛指数排名", 44, 48)): "公牛指数排名",
            }

            for future in as_completed(futures):
                task_name = futures[future]

                try:
                    success, msg = future.result()
                    if success:
                        self.results['success_items'].append(task_name)
                        self.progress.emit(0, f"{task_name}完成")  # 进度由子回调控制
                        self.sub_task_done.emit(task_name, True)
                    else:
                        self.results['failed_items'].append((task_name, msg))
                        self.progress.emit(0, f"{task_name}失败: {msg}")
                        self.sub_task_done.emit(task_name, False)
                except Exception as e:
                    self.results['failed_items'].append((task_name, str(e)))
                    self.progress.emit(0, f"{task_name}异常: {str(e)[:50]}")
                    self.sub_task_done.emit(task_name, False)

        self.parallel_end.emit()

        # --- 第2轮: cow_index 依赖 cow_traits (65-75%) ---
        self.progress.emit(65, "开始母牛指数排名...")

        try:
            success, msg = run_cow_index(project, None,
                                         self._make_sub_progress("母牛指数", 65, 75))
            if success:
                self.results['success_items'].append("母牛指数排名")
                self.progress.emit(75, "母牛指数排名完成")
            else:
                self.results['failed_items'].append(("母牛指数排名", msg))
                self.progress.emit(75, f"母牛指数排名失败: {msg}")
        except Exception as e:
            self.results['failed_items'].append(("母牛指数排名", str(e)))
            self.progress.emit(75, f"母牛指数排名异常: {str(e)[:50]}")

        self.progress.emit(75, "所有数据分析完成")

    def _phase_excel_report(self):
        """Phase 3: Excel报告 (75-90%)"""
        from core.auto_analysis_runner import run_excel_report

        self.progress.emit(75, "开始生成Excel综合报告...")

        def excel_progress(pct, msg=None):
            mapped = 75 + int(pct * 0.15)
            self.progress.emit(mapped, f"Excel报告: {msg or f'{pct}%'}")

        try:
            success, msg = run_excel_report(self.project_path, excel_progress,
                                               service_staff=self.service_staff)
            if success:
                self.results['success_items'].append("Excel综合报告")
                # 查找生成的Excel文件
                reports_dir = self.project_path / "reports"
                excel_files = list(reports_dir.glob("育种分析综合报告_*.xlsx"))
                if excel_files:
                    self.results['excel_path'] = str(max(excel_files, key=lambda p: p.stat().st_mtime))
                self.progress.emit(90, "Excel综合报告生成完成")
            else:
                self.results['failed_items'].append(("Excel综合报告", msg))
                logger.warning(f"Excel报告生成失败: {msg}")
                self.progress.emit(90, f"Excel报告生成失败: {msg}")
        except Exception as e:
            self.results['failed_items'].append(("Excel综合报告", str(e)))
            logger.warning(f"Excel报告生成异常: {e}")
            self.progress.emit(90, f"Excel报告生成异常: {str(e)[:50]}")

    def _phase_ppt_report(self):
        """Phase 4: PPT报告 (90-100%)"""
        from core.auto_analysis_runner import run_ppt_report

        # 获取牧场名称
        if len(self.farms) == 1:
            farm_name = self.farms[0].get('name', '牧场')
        else:
            farm_name = "合并牧场"

        self.progress.emit(90, "开始生成PPT汇报材料...")

        def ppt_progress(msg, pct):
            mapped = 90 + int(pct * 0.09)
            self.progress.emit(mapped, f"PPT报告: {msg or f'{pct}%'}")

        try:
            success = run_ppt_report(self.project_path, farm_name, ppt_progress,
                                       reporter_name=self.service_staff)
            if success:
                self.results['success_items'].append("PPT汇报材料")
                # 查找生成的PPT文件
                reports_dir = self.project_path / "reports"
                ppt_files = list(reports_dir.glob("*育种分析报告_*.pptx"))
                if ppt_files:
                    self.results['ppt_path'] = str(max(ppt_files, key=lambda p: p.stat().st_mtime))
                self.progress.emit(99, "PPT汇报材料生成完成")
            else:
                self.results['failed_items'].append(("PPT汇报材料", "生成失败"))
                logger.warning("PPT报告生成失败")
                self.progress.emit(99, "PPT报告生成失败")
        except Exception as e:
            self.results['failed_items'].append(("PPT汇报材料", str(e)))
            logger.warning(f"PPT报告生成异常: {e}")
            self.progress.emit(99, f"PPT报告生成异常: {str(e)[:50]}")
