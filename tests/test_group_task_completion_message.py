from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gui.farm_selection_page import (
    FarmSelectionPage,
    build_group_task_completion_lines,
)


class GroupTaskCompletionMessageTests(unittest.TestCase):
    def test_group_excel_success_explicitly_excludes_group_ppt(self):
        lines = build_group_task_completion_lines(
            {
                "completed": [{"farm_name": "牧场A"}],
                "failed": [],
                "full_analysis": True,
                "excel_path": "/tmp/group.xlsx",
            }
        )
        text = "\n".join(lines)

        self.assertIn("已生成最终牧场组汇总Excel", text)
        self.assertIn("牧场组不生成PPT", text)
        self.assertIn("PPT请按单牧场需要生成", text)

    def test_all_failed_data_only_run_never_claims_data_was_saved(self):
        failed = [
            {
                "farm_name": f"牧场{i}",
                "error": "接口母牛记录无法识别所属牧场",
            }
            for i in range(16)
        ]

        lines = build_group_task_completion_lines(
            {
                "completed": [],
                "failed": failed,
                "full_analysis": False,
                "excel_path": None,
            }
        )
        text = "\n".join(lines)

        self.assertIn("成功 0 个，失败 16 个", text)
        self.assertIn("本次没有牧场完成", text)
        self.assertNotIn("✅ 每个牧场的数据已保存", text)
        self.assertNotIn("✅ 已完成的", text)

    def test_partial_data_only_run_only_claims_completed_farms(self):
        lines = build_group_task_completion_lines(
            {
                "completed": [{"farm_name": "牧场A"}],
                "failed": [{"farm_name": "牧场B", "error": "下载失败"}],
                "full_analysis": False,
                "excel_path": None,
            }
        )
        text = "\n".join(lines)

        self.assertIn("已完成的 1 个牧场数据已保存", text)
        self.assertIn("另有 1 个牧场未完成", text)
        self.assertNotIn("每个牧场的数据已保存", text)

    def test_all_successful_data_only_run_keeps_success_message(self):
        lines = build_group_task_completion_lines(
            {
                "completed": [
                    {"farm_name": "牧场A"},
                    {"farm_name": "牧场B"},
                ],
                "failed": [],
                "full_analysis": False,
                "excel_path": None,
            }
        )

        self.assertIn(
            "✅ 每个牧场的数据已保存到独立子项目目录",
            lines,
        )

    def test_analysis_without_excel_does_not_fall_back_to_data_success(self):
        lines = build_group_task_completion_lines(
            {
                "completed": [{"farm_name": "牧场A"}],
                "failed": [],
                "full_analysis": True,
                "excel_path": None,
                "summary_error": "",
            }
        )
        text = "\n".join(lines)

        self.assertIn("最终汇总Excel未生成", text)
        self.assertNotIn("✅ 每个牧场的数据已保存", text)

    def test_memory_pressure_is_reported_as_safe_pause_not_failure(self):
        lines = build_group_task_completion_lines(
            {
                "completed": [{"farm_name": "牧场A"}],
                "failed": [
                    {
                        "farm_name": "牧场B",
                        "error": "系统可用内存持续处于危险区",
                        "memory_pressure": True,
                    }
                ],
                "full_analysis": True,
                "excel_path": None,
                "paused_for_memory": True,
                "resume_available": True,
            }
        )
        text = "\n".join(lines)

        self.assertIn("成功 1 个，安全暂停 1 个，失败 0 个", text)
        self.assertIn("批处理已安全暂停", text)
        self.assertIn("不需要重新开始", text)
        self.assertIn("释放内存后继续处理", text)
        self.assertIn("暂停任务：", text)
        self.assertNotIn("失败任务：", text)

    def test_memory_pause_dialog_can_continue_same_group_project(self):
        class FakeMessageBox:
            class ButtonRole:
                ActionRole = 1
                AcceptRole = 2

            def __init__(self, _parent):
                self.clicked = None

            def setWindowTitle(self, _title):
                pass

            def setText(self, _text):
                pass

            def addButton(self, label, _role):
                if label == "释放内存后继续处理":
                    self.clicked = label
                return label

            def exec(self):
                pass

            def clickedButton(self):
                return self.clicked

        page = MagicMock()
        page.selected_farms = {}
        page.farm_list_items = {}
        dialog = MagicMock()
        project_path = Path("/tmp/group-resume")
        result = {
            "completed": [{"farm_name": "牧场A"}],
            "failed": [
                {
                    "farm_name": "牧场B",
                    "error": "内存安全暂停",
                    "memory_pressure": True,
                }
            ],
            "full_analysis": True,
            "excel_path": None,
            "paused_for_memory": True,
            "resume_available": True,
        }

        with patch(
            "gui.farm_selection_page.QMessageBox",
            FakeMessageBox,
        ):
            FarmSelectionPage._on_group_tasks_finished(
                page,
                dialog,
                project_path,
                result,
            )

        page.continue_group_project.assert_called_once_with(project_path)


if __name__ == "__main__":
    unittest.main()
