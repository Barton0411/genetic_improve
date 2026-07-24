"""macOS 独立更新助手。

更新必须在主程序退出后替换 ``.app``。本模块启动一个与 Qt 进程分离的
系统 shell，由它等待旧进程结束、原子替换应用并重新打开新版本。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


_HELPER_SCRIPT = r"""#!/bin/sh
set -u

SOURCE_APP=$1
TARGET_APP=$2
MAIN_PID=$3
MOUNT_POINT=$4
LOG_FILE=$5
RELAUNCH=$6

log_update() {
    /bin/date "+%Y-%m-%d %H:%M:%S $1" >> "$LOG_FILE"
}

STAGED_APP="${TARGET_APP}.update-${MAIN_PID}"
BACKUP_APP="${TARGET_APP}.backup-${MAIN_PID}"

restore_backup() {
    if [ ! -e "$TARGET_APP" ] && [ -e "$BACKUP_APP" ]; then
        /bin/mv "$BACKUP_APP" "$TARGET_APP" >/dev/null 2>&1 || true
    fi
}

show_manual_fallback() {
    restore_backup
    log_update "ERROR: $1"
    /usr/bin/osascript -e 'display dialog "自动更新未能完成。程序已经关闭，请在已打开的安装窗口中把“伊利奶牛选配”拖到 Applications 文件夹。" buttons {"好"} default button "好" with icon caution' >/dev/null 2>&1 || true
    /usr/bin/open "$MOUNT_POINT" >/dev/null 2>&1 || true
    exit 1
}

case "$SOURCE_APP" in
    *.app) ;;
    *) show_manual_fallback "source is not an app bundle" ;;
esac

case "$TARGET_APP" in
    /*.app) ;;
    *) show_manual_fallback "target is not an absolute app bundle path" ;;
esac

if [ ! -d "$SOURCE_APP/Contents/MacOS" ]; then
    show_manual_fallback "source app bundle is incomplete"
fi

log_update "Waiting for application process ${MAIN_PID} to exit"
WAITED=0
while /bin/kill -0 "$MAIN_PID" >/dev/null 2>&1; do
    /bin/sleep 1
    WAITED=$((WAITED + 1))
    if [ "$WAITED" -ge 120 ]; then
        show_manual_fallback "application did not exit within 120 seconds"
    fi
done

/bin/rm -rf -- "$STAGED_APP" "$BACKUP_APP"
log_update "Copying new application to staging path"
/usr/bin/ditto "$SOURCE_APP" "$STAGED_APP" || show_manual_fallback "failed to copy new application"

if [ ! -d "$STAGED_APP/Contents/MacOS" ]; then
    show_manual_fallback "staged application validation failed"
fi

if [ -e "$TARGET_APP" ]; then
    /bin/mv "$TARGET_APP" "$BACKUP_APP" || show_manual_fallback "failed to back up current application"
fi

/bin/mv "$STAGED_APP" "$TARGET_APP" || show_manual_fallback "failed to activate new application"
/usr/bin/xattr -cr "$TARGET_APP" >/dev/null 2>&1 || true
/bin/rm -rf -- "$BACKUP_APP"

case "$MOUNT_POINT" in
    /Volumes/*) /usr/bin/hdiutil detach "$MOUNT_POINT" -quiet >/dev/null 2>&1 || true ;;
esac

log_update "Application update completed"
if [ "$RELAUNCH" = "1" ]; then
    /usr/bin/open "$TARGET_APP" >/dev/null 2>&1 || show_manual_fallback "failed to relaunch application"
fi
"""


def resolve_target_app(app_root: str, app_name: str) -> Path:
    """返回应被替换的应用包路径。"""

    detected = Path(app_root).expanduser()
    is_mounted_image = detected.is_absolute() and detected.is_relative_to(
        Path("/Volumes")
    )
    if (
        detected.suffix == ".app"
        and detected.is_absolute()
        and not is_mounted_image
    ):
        return detected
    return Path("/Applications") / app_name


def launch_macos_update(
    *,
    source_app: str,
    target_app: str,
    main_pid: int,
    mount_point: str,
    support_dir: str,
    relaunch: bool = True,
) -> subprocess.Popen:
    """启动与当前应用分离的更新助手进程。"""

    source = Path(source_app).resolve()
    target = Path(target_app).expanduser()
    mount = Path(mount_point).resolve()
    support = Path(support_dir).expanduser().resolve()

    if source.suffix != ".app" or not (source / "Contents" / "MacOS").is_dir():
        raise ValueError("更新包中的应用目录无效")
    if not target.is_absolute() or target.suffix != ".app":
        raise ValueError("当前应用安装路径无效")
    if target.parent == Path("/"):
        raise ValueError("禁止在系统根目录执行应用替换")
    if target.is_relative_to(Path("/Volumes")):
        raise ValueError("禁止替换只读安装镜像中的应用")
    if main_pid <= 0:
        raise ValueError("当前应用进程编号无效")

    support.mkdir(parents=True, exist_ok=True)
    helper_path = support / "macos_update_helper.sh"
    log_path = support / "macos_update.log"
    helper_path.write_text(_HELPER_SCRIPT, encoding="utf-8")
    helper_path.chmod(0o700)

    helper_env = os.environ.copy()
    helper_env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    return subprocess.Popen(
        [
            "/bin/sh",
            str(helper_path),
            str(source),
            str(target),
            str(main_pid),
            str(mount),
            str(log_path),
            "1" if relaunch else "0",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        env=helper_env,
    )
