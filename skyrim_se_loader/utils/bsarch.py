# SPDX-License-Identifier: MIT
"""Call BSArch CLI to unpack BSA/BA2. Flags taken from TES5Edit BSArch.dpr help text."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .deps import get_addon_prefs, resolve_bsarch_path
from .paths import expand_path


# Documented unpack usage (BSArch.dpr, TES5Edit):
#   BSArch.exe unpack <archive> [destination-folder] [-mt:yes|no]
# Destination folder should already exist; when omitted, unpacks next to the archive.
# Do NOT invent other unpack flags — pack-only options like -sse / -z / -f do not apply.


BSARCH_DOWNLOAD = "https://www.nexusmods.com/newvegas/mods/64745"
BAE_DOWNLOAD = "https://www.nexusmods.com/skyrimspecialedition/mods/974"
BSA_BROWSER_DOWNLOAD = "https://www.nexusmods.com/skyrimspecialedition/mods/1756"


@dataclass
class BsarchResult:
    ok: bool
    message: str
    command: list[str] | None = None
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def missing_bsarch_help() -> str:
    return (
        "未找到 BSArch.exe。\n"
        "1. 下载 BSArch（xEdit 团队命令行工具）：\n"
        f"   {BSARCH_DOWNLOAD}\n"
        "2. 在插件偏好 →「BSArch 可执行文件」填入 BSArch.exe 完整路径。\n"
        "3. GUI 备选：Bethesda Archive Extractor (BAE)\n"
        f"   {BAE_DOWNLOAD}\n"
        "   或 BSA Browser：\n"
        f"   {BSA_BROWSER_DOWNLOAD}\n"
        "解包命令（官方）：BSArch.exe unpack <档案> [输出目录] [-mt:yes|no]"
    )


def build_unpack_command(
    bsarch_exe: str,
    archive: str,
    destination: str,
    multithread: bool = True,
) -> list[str]:
    """Build argv for unpack. Destination must be an existing directory path."""
    cmd = [
        bsarch_exe,
        "unpack",
        archive,
        destination,
        f"-mt:{'yes' if multithread else 'no'}",
    ]
    return cmd


def list_archive(archive_path: str, *, prefs=None) -> set[str] | None:
    """Read BSArch's documented -list output; None means unknown, never absent."""
    exe = resolve_bsarch_path(prefs if prefs is not None else get_addon_prefs())
    if not exe:
        return None
    try:
        proc = subprocess.run([exe, archive_path, "-list"], capture_output=True,
                              text=True, errors="replace", timeout=60,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode:
        return None
    paths = {s.strip().replace("\\", "/").casefold() for s in proc.stdout.splitlines()}
    paths = {s for s in paths if s.startswith(("meshes/", "textures/"))}
    # A successful but unrecognized output must not silently hide resources.
    return paths if "Archive Name:" in proc.stdout and "Files:" in proc.stdout else None


def unpack_archive(
    archive_path: str,
    output_dir: str,
    *,
    prefs=None,
    multithread: bool | None = None,
    timeout: int = 600,
) -> BsarchResult:
    prefs = prefs if prefs is not None else get_addon_prefs()
    exe = resolve_bsarch_path(prefs)
    if not exe or not Path(exe).is_file():
        return BsarchResult(False, missing_bsarch_help())

    archive = expand_path(archive_path)
    dest = expand_path(output_dir)
    if not archive:
        return BsarchResult(False, "请选择要解包的 .ba2 / .bsa 文件。")
    arch = Path(archive)
    if not arch.is_file():
        return BsarchResult(False, f"档案不存在：{archive}")
    suffix = arch.suffix.lower()
    if suffix not in {".ba2", ".bsa"}:
        return BsarchResult(
            False,
            f"期望 .ba2 或 .bsa，实际为 {arch.suffix}。"
            "SE/AE 资源包通常是 .ba2（例如 Skyrim - Meshes0.ba2）。",
        )
    if not dest:
        return BsarchResult(
            False,
            "请填写解包输出目录（建议作为工作 Data 根，含 meshes/ textures/）。",
        )
    out = Path(dest)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return BsarchResult(False, f"无法创建输出目录：{exc}")

    if multithread is None:
        multithread = True if prefs is None else bool(prefs.bsarch_multithread)

    cmd = build_unpack_command(str(Path(exe)), str(arch), str(out), multithread)
    # On Windows, CREATE_NO_WINDOW avoids flashing a console; ignore elsewhere.
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
    except FileNotFoundError:
        return BsarchResult(False, missing_bsarch_help(), command=cmd)
    except subprocess.TimeoutExpired:
        return BsarchResult(
            False,
            f"BSArch 超时（>{timeout}s）。大档案可在外部终端手动运行："
            f' BSArch.exe unpack "{arch}" "{out}"',
            command=cmd,
        )
    except OSError as exc:
        return BsarchResult(False, f"无法启动 BSArch：{exc}", command=cmd)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = stderr or stdout or f"exit={proc.returncode}"
        return BsarchResult(
            False,
            f"BSArch 解包失败：{detail}",
            command=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    msg = f"已解包 {arch.name} → {out}"
    if stdout:
        msg += f"（{stdout[:200]}）"
    return BsarchResult(
        True,
        msg,
        command=cmd,
        returncode=0,
        stdout=stdout,
        stderr=stderr,
    )
