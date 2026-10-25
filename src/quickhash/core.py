"""核心逻辑：算哈希、写校验文件、按校验文件比对。

格式和 coreutils 的 sha256sum 保持一致，所以能和 `sha256sum -c` 互相认。
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ALGOS = {
    "md5": 32,
    "sha1": 40,
    "sha256": 64,
    "sha512": 128,
}
_CHUNK = 1024 * 1024  # 1 MB 一块，兼顾速度和内存


def algo_from_length(length: int) -> str | None:
    """按哈希串长度反推算法，用于 --check 时没指定 -a 的情况。"""
    for name, size in ALGOS.items():
        if size == length:
            return name
    return None


def hash_file(path: str | os.PathLike, algo: str = "sha256",
              progress: Callable[[int, int], None] | None = None) -> str:
    """算单个文件的哈希。progress(已读字节, 总字节) 只在传了回调时调用。"""
    algo = algo.lower()
    if algo not in ALGOS:
        raise ValueError(f"不支持的算法：{algo}（可用：{', '.join(ALGOS)}）")

    h = hashlib.new(algo)
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(_CHUNK)
            if not block:
                break
            h.update(block)
            done += len(block)
            if progress:
                progress(done, total)
    return h.hexdigest()


def format_line(digest: str, name: str) -> str:
    """生成一行校验记录。两个空格表示文本模式，和 coreutils 一致。"""
    return f"{digest}  {name}"


def write_checksums(files: Iterable[str | os.PathLike], output: str | os.PathLike,
                    algo: str = "sha256", base: str | os.PathLike | None = None,
                    progress: Callable[[str, int, int], None] | None = None) -> int:
    """把一批文件的哈希写成校验文件，返回写入条数。"""
    files = list(files)
    if not files:
        raise ValueError("没有可处理的文件")

    base_path = Path(base) if base else None
    lines = []
    for f in files:
        p = Path(f)
        cb = None
        if progress:
            cb = lambda done, total, _p=p: progress(_p.name, done, total)  # noqa: E731
        digest = hash_file(p, algo, cb)
        shown = str(p.relative_to(base_path)) if base_path and base_path in p.parents else p.name
        lines.append(format_line(digest, shown.replace("\\", "/")))

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


@dataclass
class CheckResult:
    name: str
    expected: str
    actual: str | None
    status: str  # "OK" / "FAILED" / "MISSING"

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def parse_checksum_file(path: str | os.PathLike) -> list[tuple[str, str]]:
    """读校验文件，返回 [(哈希, 文件名)]。空行和 # 注释会被跳过。"""
    pairs: list[tuple[str, str]] = []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 兼容 "hash  name" 和 "hash *name" 两种写法
        if "  " in line:
            digest, _, name = line.partition("  ")
        elif " " in line:
            digest, _, name = line.partition(" ")
        else:
            continue
        name = name.strip()
        if name.startswith("*"):
            name = name[1:]
        digest = digest.strip().lower()
        if name:
            pairs.append((digest, name))
    return pairs


def verify(checksum_file: str | os.PathLike, algo: str | None = None,
           root: str | os.PathLike | None = None) -> list[CheckResult]:
    """按校验文件逐个比对。文件名按校验文件所在目录解析。"""
    pairs = parse_checksum_file(checksum_file)
    if not pairs:
        raise ValueError("校验文件里没有有效记录")

    base = Path(root) if root else Path(checksum_file).resolve().parent
    results: list[CheckResult] = []

    for digest, name in pairs:
        target = (base / name) if not Path(name).is_absolute() else Path(name)
        use_algo = algo or algo_from_length(len(digest)) or "sha256"
        if not target.exists():
            results.append(CheckResult(name, digest, None, "MISSING"))
            continue
        try:
            actual = hash_file(target, use_algo)
        except OSError as e:
            results.append(CheckResult(name, digest, f"<读取失败: {e}>", "FAILED"))
            continue
        status = "OK" if actual == digest else "FAILED"
        results.append(CheckResult(name, digest, actual, status))

    return results


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"
