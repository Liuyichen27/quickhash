"""quickhash 测试：哈希向量用标准值核对，不自我循环验证。"""

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quickhash import cli, core  # noqa: E402


class TestHash(unittest.TestCase):
    def test_known_sha256_vector(self):
        # 标准测试向量：sha256("abc")
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "abc.txt"
            f.write_bytes(b"abc")
            self.assertEqual(
                core.hash_file(f, "sha256"),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

    def test_matches_hashlib_for_all_algos(self):
        data = b"x" * 100000 + b"y" * 333
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "blob.bin"
            f.write_bytes(data)
            for algo in core.ALGOS:
                with self.subTest(algo=algo):
                    want = getattr(hashlib, algo)(data).hexdigest()
                    self.assertEqual(core.hash_file(f, algo), want)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "empty.bin"
            f.write_bytes(b"")
            self.assertEqual(
                core.hash_file(f, "sha256"),
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )

    def test_bad_algo(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "a.bin"
            f.write_bytes(b"a")
            with self.assertRaises(ValueError):
                core.hash_file(f, "crc32")


class TestChecksumFile(unittest.TestCase):
    def test_roundtrip_ok(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.txt").write_text("hello", encoding="utf-8")
            (d / "b.txt").write_text("world", encoding="utf-8")
            sums = d / "sums.txt"

            n = core.write_checksums([d / "a.txt", d / "b.txt"], sums, "sha256", base=d)
            self.assertEqual(n, 2)

            results = core.verify(sums)
            self.assertEqual(len(results), 2)
            self.assertTrue(all(r.ok for r in results), [r.status for r in results])

    def test_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            target = d / "a.txt"
            target.write_text("original", encoding="utf-8")
            sums = d / "sums.txt"
            core.write_checksums([target], sums, "sha256", base=d)

            target.write_text("tampered", encoding="utf-8")
            results = core.verify(sums)
            self.assertEqual(results[0].status, "FAILED")
            self.assertNotEqual(results[0].actual, results[0].expected)

    def test_detects_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            target = d / "gone.txt"
            target.write_text("x", encoding="utf-8")
            sums = d / "sums.txt"
            core.write_checksums([target], sums, "sha256", base=d)
            target.unlink()

            results = core.verify(sums)
            self.assertEqual(results[0].status, "MISSING")

    def test_parses_binary_marker_and_comments(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "sums.txt"
            f.write_text(
                "# 这是注释\n"
                "\n"
                "d41d8cd98f00b204e9800998ecf8427e  a.txt\n"
                "d41d8cd98f00b204e9800998ecf8427e *b.txt\n",
                encoding="utf-8",
            )
            pairs = core.parse_checksum_file(f)
            self.assertEqual([name for _, name in pairs], ["a.txt", "b.txt"])

    def test_infers_algo_from_length(self):
        self.assertEqual(core.algo_from_length(32), "md5")
        self.assertEqual(core.algo_from_length(40), "sha1")
        self.assertEqual(core.algo_from_length(64), "sha256")
        self.assertEqual(core.algo_from_length(128), "sha512")
        self.assertIsNone(core.algo_from_length(13))

    def test_md5_check_works_without_algo_flag(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.txt").write_text("abc", encoding="utf-8")
            sums = d / "md5.txt"
            core.write_checksums([d / "a.txt"], sums, "md5", base=d)
            self.assertEqual(core.verify(sums)[0].status, "OK")

    def test_compatible_with_coreutils_format(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "f.txt").write_text("abc", encoding="utf-8")
            sums = d / "s.txt"
            core.write_checksums([d / "f.txt"], sums, "sha256", base=d)
            line = sums.read_text(encoding="utf-8").strip()
            self.assertEqual(line.split("  ")[1], "f.txt")
            self.assertEqual(len(line.split("  ")[0]), 64)


class TestCli(unittest.TestCase):
    def test_save_then_check(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.bin").write_bytes(b"payload")
            sums = d / "sums.txt"
            self.assertEqual(cli.main([str(d / "a.bin"), "--save", str(sums)]), 0)
            self.assertTrue(sums.exists())
            self.assertEqual(cli.main(["--check", str(sums)]), 0)

    def test_check_returns_1_on_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            f = d / "a.bin"
            f.write_bytes(b"one")
            sums = d / "sums.txt"
            cli.main([str(f), "--save", str(sums)])
            f.write_bytes(b"two")
            self.assertEqual(cli.main(["--check", str(sums)]), 1)

    def test_no_args_returns_2(self):
        self.assertEqual(cli.main([]), 2)


if __name__ == "__main__":
    unittest.main()
