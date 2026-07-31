"""
自动报告生成工作线程

在后台执行完整流程：数据下载 → 标准化 → 7项数据分析 → Excel报告 → PPT报告
"""

import gc
import inspect
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import QThread, pyqtSignal
from core.group_tasks.dataset_plan import (
    BREEDING_RAW_RECEIPT,
    BREEDING_STANDARDIZED_RECEIPT,
    normalize_dataset_selection,
    write_empty_breeding_receipts,
)
from core.group_tasks.memory_guard import ResourcePressureError

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

    def __init__(
        self,
        api_client,
        farms,
        project_path,
        is_merged=False,
        service_staff=None,
        data_source="伊起牛",
        local_farms=None,
        reliability_mode=False,
        group_batch_mode=False,
        resource_check=None,
        dataset_selection=None,
    ):
        """
        初始化

        Args:
            api_client: YQN API客户端
            farms: 牧场列表 [{"code": ..., "name": ..., "cow_count": ...}, ...]
            project_path: 项目路径
            is_merged: 是否为合并模式
            service_staff: 服务人员姓名（登录用户）
            reliability_mode: 低内存可靠模式；牧场组逐场处理时启用
            group_batch_mode: 牧场组批量分析模式；不执行或汇入个体选配
            dataset_selection: 固定 ``herd/breeding`` 数据集选择；旧调用
                未传时按历史行为两项全选。
        """
        super().__init__()
        self.api_client = api_client
        self.farms = farms
        self.project_path = Path(project_path)
        self.is_merged = is_merged
        self.service_staff = service_staff
        self.data_source = data_source
        self.local_farms = local_farms or []
        # 牧场组逐场处理时启用：优先控制内存峰值和跨牧场状态隔离。
        # 默认关闭，保持原有单牧场并发行为不变。
        self.reliability_mode = bool(reliability_mode)
        self.group_batch_mode = bool(group_batch_mode)
        # 牧场组数据阶段仍需复用当前登录态，暂时运行在桌面工作线程内。
        # 由调用方注入轻量检查点，在下载、转换和标准化步骤之间及时
        # 暂停；单牧场流程不传该回调，保持原行为。
        self.resource_check = resource_check
        self.dataset_selection = normalize_dataset_selection(
            dataset_selection,
            has_local_farms=bool(self.local_farms),
        )

        # 各步骤结果跟踪
        self.results = {
            'success_items': [],   # 成功的步骤
            'failed_items': [],    # 失败的步骤 [(步骤名, 错误信息)]
            'excel_path': None,    # Excel报告路径
            'ppt_path': None,      # PPT报告路径
        }

    def _check_resources(self):
        if self.resource_check is not None:
            self.resource_check()

    def _make_sub_progress(self, task_name, start_pct, end_pct):
        """创建子任务进度回调，将 0-100% 映射到全局 start_pct-end_pct"""
        def callback(sub_pct, msg=""):
            # 容忍 None：底层有些模块会传 progress_callback(None, "出错: ...") 表示异常状态，
            # 此时不应该再爆 None/int 错误掩盖真正的异常 message
            if sub_pct is None:
                self.progress.emit(start_pct, f"[{task_name}] {msg}")
                return
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
            results = self.execute()
            self.finished.emit(results)

        except Exception as e:
            logger.exception("自动报告生成失败")
            self.error.emit(f"自动报告生成失败: {str(e)}")

    def execute(
        self,
        *,
        download: bool = True,
        analysis: bool = True,
        excel: bool = True,
        ppt: bool = True,
    ) -> dict:
        """同步执行指定阶段，供牧场组工作线程逐场复用。"""
        try:
            if download:
                self._check_resources()
                self._phase_download_and_standardize()
                self._check_resources()
                self._release_phase_resources()
            if analysis:
                if not self.dataset_selection["herd"]:
                    raise ValueError(
                        "未选择牛群/系谱数据，不能执行育种分析"
                    )
                self._phase_analysis()
                try:
                    from core.group_tasks.manual_stage_bridge import (
                        commit_manual_group_analysis_if_ready,
                    )

                    commit_manual_group_analysis_if_ready(
                        self.project_path
                    )
                except Exception as bridge_error:
                    logger.info(
                        "当前分析结果尚不能提交牧场组阶段: %s",
                        bridge_error,
                    )
                self._release_phase_resources(reset_pedigree=True)
            if excel:
                self._phase_excel_report()
                self._release_phase_resources()
            if ppt:
                self._phase_ppt_report()
                self._release_phase_resources()
            self.progress.emit(100, "全部完成!")
            return self.results
        finally:
            # 异常中断时也必须释放全局系谱对象，避免下一个牧场继承本场
            # 母牛节点；同时回收 Excel/PPT 生成过程中可能形成的引用环。
            self._release_phase_resources(reset_pedigree=True)

    def _release_phase_resources(self, *, reset_pedigree=False):
        """可靠模式下清理单场阶段资源，降低牧场组长期运行的内存峰值。"""
        if not self.reliability_mode:
            return

        if reset_pedigree:
            try:
                from core.data.update_manager import reset_pedigree_db

                reset_pedigree_db()
            except Exception as exc:
                # 清理失败不应把已完成的业务计算标记为失败。
                logger.warning("释放系谱缓存失败（继续处理）: %s", exc)

        gc.collect()

    def _dataset_progress(self, label, start_pct, end_pct):
        def callback(*args):
            self._check_resources()
            if not args:
                return
            value = args[0]
            message = args[1] if len(args) > 1 else value
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                self.progress.emit(start_pct, f"{label}: {message}")
                return
            mapped = start_pct + int(
                numeric / 100 * (end_pct - start_pct)
            )
            self.progress.emit(mapped, f"{label}: {message}")

        return callback

    def _clear_breeding_receipts(self):
        for relative in (
            BREEDING_RAW_RECEIPT,
            BREEDING_STANDARDIZED_RECEIPT,
        ):
            (self.project_path / relative).unlink(missing_ok=True)

    def _record_empty_breeding_result(self):
        """保存接口成功返回 0 条的事实，并隔离旧配种结果。"""
        for relative in (
            Path("raw_data") / "breeding_records.xlsx",
            Path("standardized_data") / "processed_breeding_data.xlsx",
        ):
            (self.project_path / relative).unlink(missing_ok=True)
        write_empty_breeding_receipts(
            self.project_path,
            data_source=self.data_source,
            farms=self.farms,
        )

    def _isolate_unselected_dataset_outputs(self):
        """未选择的数据集不能被旧文件冒充为本轮结果。"""
        per_farm_root = self.project_path / "raw_data" / "farms"
        for filename in ("cow_data.xlsx", "breeding_records.xlsx"):
            if per_farm_root.is_dir():
                for path in per_farm_root.glob(f"*/{filename}"):
                    path.unlink(missing_ok=True)
        if not self.dataset_selection["herd"]:
            for relative in (
                Path("raw_data") / "cow_data.xlsx",
                Path("standardized_data") / "processed_cow_data.xlsx",
            ):
                (self.project_path / relative).unlink(missing_ok=True)
        if not self.dataset_selection["breeding"]:
            for relative in (
                Path("raw_data") / "breeding_records.xlsx",
                Path("standardized_data")
                / "processed_breeding_data.xlsx",
                BREEDING_RAW_RECEIPT,
                BREEDING_STANDARDIZED_RECEIPT,
            ):
                (self.project_path / relative).unlink(missing_ok=True)

    def _download_yqn_stock(self, raw_data_dir, converter):
        """保留旧单牧场库存能力；牧场组批量阶段不会调用。"""
        self.progress.emit(25, "正在下载冻精库存...")
        try:
            all_stock_records = []
            for farm in self.farms:
                self._check_resources()
                stock_data = self.api_client.get_stock_detail(farm["code"])
                self._check_resources()
                all_stock_records.extend(stock_data.get("data", []))
            if not all_stock_records:
                return
            semen_inventory_path = raw_data_dir / "semen_inventory.xlsx"
            converter.convert_stock_to_semen_inventory(
                {"code": 200, "data": all_stock_records},
                semen_inventory_path,
            )
            from core.data.uploader import (
                upload_and_standardize_bull_data,
            )

            upload_and_standardize_bull_data(
                input_files=[semen_inventory_path],
                project_path=self.project_path,
                progress_callback=self._dataset_progress(
                    "标准化冻精库存",
                    26,
                    28,
                ),
            )
            self._check_resources()
        except (MemoryError, ResourcePressureError):
            raise
        except Exception as exc:
            logger.warning("冻精库存处理失败（不影响主流程）: %s", exc)

    def _selected_dataset_success_message(self):
        selected = []
        if self.dataset_selection["herd"]:
            selected.append("牛群/系谱")
        if self.dataset_selection["breeding"]:
            selected.append("配种记录")
        return "、".join(selected) + "下载与标准化"

    def _phase_download_and_standardize(self):
        """Phase 1: 数据下载与标准化 (0-30%)"""
        self._check_resources()
        if self.data_source == "慧牧云":
            return self._phase_download_and_standardize_hmy()

        from core.data.yqn_data_converter import YQNDataConverter
        raw_data_dir = self.project_path / "raw_data"
        raw_data_dir.mkdir(parents=True, exist_ok=True)
        total_farms = max(len(self.farms), 1)
        want_herd = self.dataset_selection["herd"]
        want_breeding = self.dataset_selection["breeding"]

        self._isolate_unselected_dataset_outputs()

        if want_herd:
            from core.data.uploader import upload_and_standardize_cow_data

            all_api_data = []
            for index, farm in enumerate(self.farms):
                self._check_resources()
                pct = int(index / total_farms * 7)
                self.progress.emit(
                    pct,
                    f"正在下载 {farm['name']} 牛群数据...",
                )
                api_data = self.api_client.get_farm_herd(farm["code"])
                self._check_resources()
                records = api_data.get("data") or []
                if not isinstance(records, list):
                    raise ValueError("牛群接口返回格式无效")
                farm["cow_count"] = len(records)
                all_api_data.append((farm["code"], api_data))
                if records:
                    farm_raw_dir = (
                        raw_data_dir / "farms" / str(farm["code"])
                    )
                    YQNDataConverter.convert_herd_to_excel(
                        api_data,
                        farm_raw_dir / "cow_data.xlsx",
                    )

            merged_herd = (
                YQNDataConverter.merge_herd_data(all_api_data)
                if self.is_merged
                else all_api_data[0][1]
            )
            herd_excel = raw_data_dir / "cow_data.xlsx"
            YQNDataConverter.convert_herd_to_excel(
                merged_herd,
                herd_excel,
            )
            self._check_resources()
            self.progress.emit(8, "正在标准化牛群数据...")
            upload_and_standardize_cow_data(
                input_files=[herd_excel],
                project_path=self.project_path,
                progress_callback=self._dataset_progress(
                    "标准化牛群",
                    8,
                    19,
                ),
                source_system="伊起牛",
            )
            self._check_resources()

        if want_breeding:
            from core.data.uploader import (
                upload_and_standardize_breeding_data,
            )

            all_breeding_data = []
            retrieved_count = 0
            for index, farm in enumerate(self.farms):
                self._check_resources()
                pct = 19 + int(index / total_farms * 4)
                self.progress.emit(
                    pct,
                    f"正在下载 {farm['name']} 配种记录...",
                )
                breeding_data = self.api_client.get_breeding_records(
                    farm["code"]
                )
                self._check_resources()
                data = breeding_data.get("data", {})
                if not isinstance(data, dict):
                    raise ValueError("配种记录接口返回格式无效")
                records = data.get("rows") or []
                if not isinstance(records, list):
                    raise ValueError("配种记录接口 rows 格式无效")
                farm["breeding_count"] = len(records)
                retrieved_count += len(records)
                all_breeding_data.append((farm["code"], breeding_data))
                if records:
                    farm_raw_dir = (
                        raw_data_dir / "farms" / str(farm["code"])
                    )
                    YQNDataConverter.convert_breeding_records_to_excel(
                        breeding_data,
                        farm_raw_dir / "breeding_records.xlsx",
                    )

            merged_breeding = YQNDataConverter.merge_breeding_records(
                all_breeding_data,
                force_prefix=self.is_merged,
            )
            if len(merged_breeding) != retrieved_count:
                raise ValueError(
                    "配种记录合并数量与接口返回数量不一致"
                )
            breeding_excel = raw_data_dir / "breeding_records.xlsx"
            if merged_breeding:
                self._clear_breeding_receipts()
                YQNDataConverter.convert_breeding_records_to_excel(
                    {"data": {"rows": merged_breeding}},
                    breeding_excel,
                )
                self.progress.emit(23, "正在标准化配种记录...")
                upload_and_standardize_breeding_data(
                    input_files=[breeding_excel],
                    project_path=self.project_path,
                    progress_callback=self._dataset_progress(
                        "标准化配种记录",
                        23,
                        27,
                    ),
                    source_system="伊起牛",
                    require_cow=want_herd,
                )
            else:
                self._record_empty_breeding_result()
            self._check_resources()

        # 冻精库存不属于本次牧场组可选数据集；批量数据阶段不得隐式
        # 请求它。旧的单牧场流程仍保留原行为。
        if not self.group_batch_mode and want_herd:
            self._download_yqn_stock(raw_data_dir, YQNDataConverter)

        from core.data.composite_farm_manager import (
            finalize_breeding_only_project,
            finalize_composite_project,
        )

        self._check_resources()

        def finalize_progress(pct, msg):
            self._check_resources()
            self.progress.emit(28 + int(pct * 0.02), msg)

        if want_herd:
            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="伊起牛",
                ids_are_prefixed=self.is_merged,
                progress_callback=finalize_progress,
                dataset_selection=self.dataset_selection,
            )
        else:
            finalize_breeding_only_project(
                self.project_path,
                self.farms,
                "伊起牛",
                ids_are_prefixed=self.is_merged,
                progress_callback=finalize_progress,
                dataset_selection=self.dataset_selection,
            )
        self._check_resources()
        self.results["success_items"].append(
            self._selected_dataset_success_message()
        )
        if want_breeding:
            breeding_output = (
                self.project_path
                / "standardized_data"
                / "processed_breeding_data.xlsx"
            )
            self.results["success_items"].append(
                "配种记录下载与标准化"
                if breeding_output.is_file()
                else "配种记录接口返回 0 条，已保存完成回执"
            )
        self.progress.emit(30, "数据下载与标准化完成")

    def _phase_download_and_standardize_hmy(self):
        """按固定选择下载并标准化慧牧云数据集。"""
        from core.data.hmy_data_converter import HMYDataConverter
        from core.data.uploader import (
            upload_and_standardize_breeding_data,
            upload_and_standardize_cow_data,
        )

        raw_dir = self.project_path / "raw_data"
        raw_dir.mkdir(parents=True, exist_ok=True)
        total_farms = max(len(self.farms), 1)
        want_herd = self.dataset_selection["herd"]
        want_breeding = self.dataset_selection["breeding"]
        self._isolate_unselected_dataset_outputs()

        if want_herd:
            all_api_data = []
            for index, farm in enumerate(self.farms):
                self._check_resources()
                pct = int(index / total_farms * 8)
                self.progress.emit(
                    pct,
                    f"正在下载 {farm['name']} 牛群数据...",
                )
                api_data = self.api_client.get_farm_herd(farm["code"])
                self._check_resources()
                records = api_data.get("data") or []
                if not isinstance(records, list):
                    raise ValueError("慧牧云牛群接口返回格式无效")
                api_farm_name = str(
                    api_data.get("farmName") or ""
                ).strip()
                if api_farm_name:
                    farm["name"] = api_farm_name
                farm["cow_count"] = len(records)
                all_api_data.append((farm["code"], api_data))
                if records:
                    farm_raw_dir = (
                        raw_dir / "farms" / str(farm["code"])
                    )
                    HMYDataConverter.convert_herd_to_excel(
                        api_data,
                        farm_raw_dir / "cow_data.xlsx",
                    )

            merged_data = (
                HMYDataConverter.merge_herd_data(all_api_data)
                if self.is_merged
                else all_api_data[0][1]
            )
            excel_path = raw_dir / "cow_data.xlsx"
            HMYDataConverter.convert_herd_to_excel(
                merged_data,
                excel_path,
            )
            self.progress.emit(9, "正在标准化慧牧云牛群数据...")
            upload_and_standardize_cow_data(
                input_files=[excel_path],
                project_path=self.project_path,
                progress_callback=self._dataset_progress(
                    "标准化牛群",
                    9,
                    19,
                ),
                source_system="慧牧云",
            )
            self._check_resources()

        if want_breeding:
            all_breeding_data = []
            retrieved_count = 0
            for index, farm in enumerate(self.farms):
                self._check_resources()
                pct = 19 + int(index / total_farms * 4)
                self.progress.emit(
                    pct,
                    f"正在下载 {farm['name']} 配种记录...",
                )
                breeding_data = self.api_client.get_breeding_records(
                    farm["code"]
                )
                self._check_resources()
                records = breeding_data.get("data") or []
                if not isinstance(records, list):
                    raise ValueError("慧牧云配种记录接口返回格式无效")
                farm["breeding_count"] = len(records)
                retrieved_count += len(records)
                all_breeding_data.append(
                    (farm["code"], breeding_data)
                )
                if records:
                    farm_raw_dir = (
                        raw_dir / "farms" / str(farm["code"])
                    )
                    HMYDataConverter.convert_breeding_records_to_excel(
                        breeding_data,
                        farm_raw_dir / "breeding_records.xlsx",
                    )
                self._check_resources()

            merged_breeding = HMYDataConverter.merge_breeding_records(
                all_breeding_data,
                force_prefix=self.is_merged,
            )
            merged_records = merged_breeding.get("data") or []
            if len(merged_records) != retrieved_count:
                raise ValueError(
                    "慧牧云配种记录合并数量与接口返回数量不一致"
                )
            if merged_records:
                self._clear_breeding_receipts()
                breeding_excel_path = raw_dir / "breeding_records.xlsx"
                HMYDataConverter.convert_breeding_records_to_excel(
                    merged_breeding,
                    breeding_excel_path,
                )
                upload_and_standardize_breeding_data(
                    input_files=[breeding_excel_path],
                    project_path=self.project_path,
                    progress_callback=self._dataset_progress(
                        "标准化配种记录",
                        23,
                        27,
                    ),
                    source_system="慧牧云",
                    require_cow=want_herd,
                )
            else:
                self._record_empty_breeding_result()
            self._check_resources()

        from core.data.composite_farm_manager import (
            finalize_breeding_only_project,
            finalize_composite_project,
        )

        self._check_resources()

        def finalize_progress(pct, msg):
            self._check_resources()
            self.progress.emit(28 + int(pct * 0.02), msg)

        if want_herd:
            finalize_composite_project(
                self.project_path,
                self.farms,
                self.local_farms,
                data_source="慧牧云",
                ids_are_prefixed=self.is_merged,
                progress_callback=finalize_progress,
                dataset_selection=self.dataset_selection,
            )
        else:
            finalize_breeding_only_project(
                self.project_path,
                self.farms,
                "慧牧云",
                ids_are_prefixed=self.is_merged,
                progress_callback=finalize_progress,
                dataset_selection=self.dataset_selection,
            )
        self._check_resources()
        self.results["success_items"].append(
            self._selected_dataset_success_message()
        )
        if want_breeding:
            breeding_output = (
                self.project_path
                / "standardized_data"
                / "processed_breeding_data.xlsx"
            )
            self.results["success_items"].append(
                "配种记录下载与标准化"
                if breeding_output.is_file()
                else "配种记录接口返回 0 条，已保存完成回执"
            )
        if want_herd:
            self.results["success_items"].append(
                "冻精库存不可用，备选公牛需手动上传"
            )
        self.progress.emit(30, "慧牧云所选数据准备完成")

    def _phase_analysis(self):
        """Phase 2: 数据分析 (30-75%)

        优化：将原来3轮串行改为2轮。
        唯一真实依赖：cow_index 需要 cow_traits 输出，其余6个任务完全独立。

        第1轮 (30-65%): 7个独立任务并行
          cow_traits, cow_self_inbreeding, bull_traits,
          mated_bull_traits, bull_index, inbreeding_mated,
          inbreeding_candidate
        第2轮 (65-75%): cow_index (依赖 cow_traits)
        """
        from core.auto_analysis_runner import (
            run_cow_traits, run_bull_traits, run_mated_bull_traits,
            run_cow_index, run_bull_index, run_inbreeding_analysis,
            run_cow_self_inbreeding_analysis,
        )

        project = str(self.project_path)
        if self.group_batch_mode:
            self.results["success_items"].append(
                "牧场组批量任务未执行个体选配（请进入单牧场子项目操作）"
            )
            self.progress.emit(
                30,
                "牧场组仅批量执行育种分析，个体选配需在单牧场子项目中完成",
            )

        standardized = self.project_path / "standardized_data"
        has_bulls = (standardized / "processed_bull_data.xlsx").exists()
        has_breeding = (
            self.dataset_selection["breeding"]
            and (
                standardized / "processed_breeding_data.xlsx"
            ).exists()
        )

        task_specs = [
            (
                "母牛性状分析",
                run_cow_traits,
                (project, None, self._make_sub_progress("母牛性状分析", 30, 65)),
            ),
            (
                "母牛近交分析",
                run_cow_self_inbreeding_analysis,
                (
                    project,
                    self._make_sub_progress(
                        "母牛近交分析",
                        30,
                        65,
                    ),
                ),
            ),
        ]
        if has_bulls:
            task_specs.extend(
                [
                    (
                        "备选公牛性状分析",
                        run_bull_traits,
                        (project, None, self._make_sub_progress("备选公牛性状分析", 30, 65)),
                    ),
                    (
                        "公牛指数排名",
                        run_bull_index,
                        (project, None, self._make_sub_progress("公牛指数排名", 30, 65)),
                    ),
                    (
                        "备选公牛近交分析",
                        run_inbreeding_analysis,
                        (
                            project,
                            "candidate",
                            self._make_sub_progress("备选公牛近交分析", 30, 65),
                        ),
                    ),
                ]
            )
        else:
            self.results["success_items"].append("备选公牛数据未上传，相关分析已跳过")

        if has_breeding:
            task_specs.extend(
                [
                    (
                        "已配公牛性状分析",
                        run_mated_bull_traits,
                        (project, None, self._make_sub_progress("已配公牛性状分析", 30, 65)),
                    ),
                    (
                        "已配公牛近交分析",
                        run_inbreeding_analysis,
                        (
                            project,
                            "mated",
                            self._make_sub_progress("已配公牛近交分析", 30, 65),
                        ),
                    ),
                ]
            )
        else:
            self.results["success_items"].append("配种记录不可用，已配公牛分析已跳过")

        task_display_names = [spec[0] for spec in task_specs]
        execution_label = "低内存顺序执行" if self.reliability_mode else "并行"
        self.progress.emit(
            30,
            f"开始数据分析（{len(task_specs)}项，{execution_label}）...",
        )
        self.parallel_start.emit(task_display_names)

        analysis_workers = (
            1 if self.reliability_mode else max(1, len(task_specs))
        )
        with ThreadPoolExecutor(max_workers=analysis_workers) as executor:
            futures = {
                executor.submit(function, *args): name
                for name, function, args in task_specs
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
            if len(self.farms) == 1:
                farm_name = self.farms[0].get('name', '牧场')
            else:
                farm_name = "合并牧场"
            report_kwargs = {
                "service_staff": self.service_staff,
                "farm_name": farm_name,
            }
            report_parameters = inspect.signature(
                run_excel_report
            ).parameters
            if "include_mating" in report_parameters:
                report_kwargs["include_mating"] = not self.group_batch_mode
            # 向后兼容：当前报告入口尚未开放并发参数；一旦入口支持，
            # 可靠模式会自动把内部 collector 并发降为 1。
            if self.reliability_mode:
                if "max_workers" in report_parameters:
                    report_kwargs["max_workers"] = 1
                if "reliability_mode" in report_parameters:
                    report_kwargs["reliability_mode"] = True

            success, msg = run_excel_report(
                self.project_path,
                excel_progress,
                **report_kwargs,
            )
            if success:
                self.results['success_items'].append("Excel综合报告")
                # 查找生成的Excel文件
                reports_dir = self.project_path / "reports"
                excel_files = list(reports_dir.glob("育种分析综合报告_*.xlsx"))
                if excel_files:
                    latest_excel = max(
                        excel_files,
                        key=lambda p: p.stat().st_mtime,
                    )
                    self.results['excel_path'] = str(latest_excel)
                    try:
                        from core.group_tasks.manual_stage_bridge import (
                            commit_manual_group_excel_if_ready,
                        )

                        commit_manual_group_excel_if_ready(
                            self.project_path,
                            latest_excel,
                        )
                    except Exception as bridge_error:
                        logger.info(
                            "单场Excel已生成，但暂未提交牧场组阶段: %s",
                            bridge_error,
                        )
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
