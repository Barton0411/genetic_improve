from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as application_main

from core.group_tasks.parent_process import (
    ChildProtocolError,
    build_child_command,
    build_child_request,
    parse_jsonl_line,
    parse_jsonl_lines,
    write_child_request,
)
from utils.file_manager import FileManager


class GroupChildEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temporary_dir.name)
        project = FileManager.create_group_project(
            self.base_path,
            [{"code": "1001", "name": "测试牧场"}],
            data_source="伊起牛",
            task_mode="analysis",
        )
        self.parent = project.resolve(strict=True)
        self.task = FileManager.load_project_metadata(project)[
            "group_tasks"
        ][0]

    def tearDown(self):
        self.temporary_dir.cleanup()

    def test_main_hidden_entry_dispatches_before_gui_main(self):
        protocol = io.StringIO()
        with (
            patch(
                "main._open_child_protocol_stdout",
                return_value=(protocol, False),
            ),
            patch(
                "core.group_tasks.child_runner.main",
                return_value=7,
            ) as runner,
        ):
            exit_code = application_main.main(
                ["--group-child-runner", "/tmp/request.json"]
            )
        self.assertEqual(exit_code, 7)
        runner.assert_called_once_with(
            ["/tmp/request.json"],
            output_stream=protocol,
        )

    def test_normal_arguments_do_not_enter_hidden_mode(self):
        self.assertIsNone(
            application_main.dispatch_group_child_runner(["--normal-start"])
        )

    def test_builds_valid_credential_free_request_and_commands(self):
        request = build_child_request(
            self.parent,
            self.task["task_id"],
            ["analysis", "child_excel"],
            service_staff="测试人员",
        )
        self.assertEqual(
            set(request),
            {
                "schema_version",
                "task_id",
                "farm_code",
                "project_path",
                "stages",
                "service_staff",
            },
        )
        request_path = write_child_request(
            self.parent,
            self.task["task_id"],
            ["analysis"],
            service_staff="测试人员",
        )
        saved = json.loads(request_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["farm_code"], "1001")
        self.assertEqual(saved["service_staff"], "测试人员")
        if os.name != "nt":
            self.assertEqual(request_path.stat().st_mode & 0o777, 0o600)

        source_command = build_child_command(
            request_path,
            executable="/python",
            frozen=False,
        )
        self.assertEqual(
            source_command[0],
            "/python",
        )
        self.assertTrue(source_command[1].endswith("/main.py"))
        self.assertEqual(source_command[2], "--group-child-runner")
        frozen_command = build_child_command(
            request_path,
            executable="/application",
            frozen=True,
        )
        self.assertEqual(
            frozen_command[:2],
            ["/application", "--group-child-runner"],
        )

    def test_parses_jsonl_strictly(self):
        events = list(
            parse_jsonl_lines(
                [
                    '{"type":"progress","progress":50}\n',
                    b'{"type":"result","success":true}\n',
                ]
            )
        )
        self.assertEqual(events[0]["progress"], 50)
        self.assertTrue(events[1]["success"])
        with self.assertRaises(ChildProtocolError):
            parse_jsonl_line("legacy print output")
        with self.assertRaises(ChildProtocolError):
            parse_jsonl_line('{"type":"progress","progress":101}')
        with self.assertRaises(ChildProtocolError):
            parse_jsonl_line('{"type":"result","success":"yes"}')


if __name__ == "__main__":
    unittest.main()
