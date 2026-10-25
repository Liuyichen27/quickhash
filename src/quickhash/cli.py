"""quickhash 命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, _update, core

_PROGRESS_THRESHOLD = 128 * 1024 * 1024  # 超过 128 MB 才显示进度，免得刷屏


def _progress_printer(label: str):
    """返回一个进度回调；不是终端就什么也不做。"""

    def cb(done: int, total: int) -> None:
        if not sys.stderr.isatty() or total <= 0:
            return
        pct = done / total * 100
        bar_len = 24
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stderr.write(f"\r  {label[:24]:<24} {bar} {pct:5.1f}%")
        sys.stderr.flush()
        if done >= total:
            sys.stderr.write("\n")

    return cb


def collect(paths: list[str], recursive: bool) -> list[Path]:
    """把文件/目录摊平。目录里的隐藏文件也收，但跳过常见的垃圾目录。"""
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    out: list[Path] = []
    for p in paths:
        path = Path(p).expanduser()
        if path.is_file():
            out.append(path)
        elif path.is_dir():
            it = path.rglob("*") if recursive else path.glob("*")
            for f in it:
                if not f.is_file():
                    continue
                if any(part in skip_dirs for part in f.parts):
                    continue
                out.append(f)
        else:
            print(f"跳过（不存在）：{path}", file=sys.stderr)
    seen: set[Path] = set()
    uniq: list[Path] = []
    for f in out:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(f)
    return uniq


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quickhash",
        description="算文件哈希、生成校验文件、按校验文件比对。格式兼容 sha256sum。",
        epilog="例子：quickhash 镜像.iso --save sha256sums.txt",
    )
    p.add_argument("paths", nargs="*", help="要计算哈希的文件或目录")
    p.add_argument("-a", "--algo", default="sha256",
                   choices=sorted(core.ALGOS), help="哈希算法（默认 sha256）")
    p.add_argument("-r", "--recursive", action="store_true", help="递归处理子目录")
    p.add_argument("-s", "--save", metavar="FILE", help="把结果写成校验文件")
    p.add_argument("-c", "--check", metavar="FILE", help="按校验文件验证指定文件")
    p.add_argument("-q", "--quiet", action="store_true", help="只输出哈希值本身")
    p.add_argument("-V", "--version", action="version", version=f"quickhash {__version__}")
    return p


def do_check(checksum_file: str, algo: str | None) -> int:
    try:
        results = core.verify(checksum_file, algo)
    except FileNotFoundError:
        print(f"找不到校验文件：{checksum_file}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2

    for r in results:
        if r.status == "OK":
            print(f"{r.name}: OK")
        elif r.status == "MISSING":
            print(f"{r.name}: FAILED（文件不存在）")
        else:
            print(f"{r.name}: FAILED")
            if r.actual:
                print(f"  期望 {r.expected}")
                print(f"  实际 {r.actual}")

    bad = [r for r in results if not r.ok]
    print()
    if bad:
        print(f"{len(results) - len(bad)} 个通过，{len(bad)} 个失败")
        return 1
    print(f"全部 {len(results)} 个文件校验通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        return do_check(args.check, args.algo)

    if not args.paths:
        build_parser().print_help(sys.stderr)
        return 2

    files = collect(args.paths, args.recursive)
    if not files:
        print("没有找到可处理的文件", file=sys.stderr)
        return 2

    if args.save:
        def progress(name: str, done: int, total: int) -> None:
            if total > _PROGRESS_THRESHOLD:
                _progress_printer(name)(done, total)

        try:
            # 以第一个目录为基准，校验文件里写相对路径，搬到别的目录也能用
            first = Path(args.paths[0]).expanduser()
            base = first if first.is_dir() else None
            n = core.write_checksums(files, args.save, args.algo, base, progress)
        except (ValueError, OSError) as e:
            print(f"错误：{e}", file=sys.stderr)
            return 1
        print(f"已写入 {n} 条记录 → {args.save}")
        return 0

    # 直接打印哈希
    failed = 0
    for f in files:
        try:
            size = f.stat().st_size
            cb = _progress_printer(f.name) if size > _PROGRESS_THRESHOLD else None
            digest = core.hash_file(f, args.algo, cb)
            print(f"{digest}  {f.name}" if args.quiet else f"{digest}  {f}")
        except OSError as e:
            print(f"读取失败：{f}（{e}）", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
