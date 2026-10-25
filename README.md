# QuickHash · 文件校验一把梭

[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-12B76A)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-12B76A)](#)

算哈希、生成校验文件、验证下载的东西有没有坏——**零依赖**，纯标准库，装上就能用。

```bash
quickhash 系统镜像.iso --save sha256sums.txt
quickhash --check sha256sums.txt
```

## 为什么用它

下载大文件最烦的两件事：一是不知道下完整没有，二是下载页给的校验码要自己一条条对。

QuickHash 把这两件事变成两条命令。而且它写出的校验文件**格式和 coreutils 的 `sha256sum` 完全一致**，所以：

- 别人用 `sha256sum -c` 能验你生成的文件
- 你用 `quickhash --check` 也能验别人（比如 Linux 发行版）给的 `SHA256SUMS`

不想被 Python 绑住？Windows 上 `certutil -hashfile` 一次只能算一个文件，还没有校验文件的概念；macOS 的 `shasum` 语法又和 Linux 不一样。QuickHash 三个平台一套命令。

## 安装

```bash
pip install git+https://github.com/Liuyichen27/quickhash.git
```

或者直接跑源码，不用装：

```bash
git clone https://github.com/Liuyichen27/quickhash.git
python quickhash/src/quickhash/cli.py --help
```

## 用法

### 算哈希

```bash
quickhash 文件.zip
# 8f4a…c21b  文件.zip

quickhash 目录/ -r                # 递归整个目录
quickhash a.bin b.bin -a md5      # 换算法
quickhash 大文件.iso              # 超过 128 MB 自动显示进度条
```

支持的算法：`md5`、`sha1`、`sha256`（默认）、`sha512`。

### 生成校验文件

```bash
quickhash 安装包/ -r --save SHA256SUMS
```

```
已写入 37 条记录 → SHA256SUMS
```

以第一个参数（目录）为基准写**相对路径**，所以整个文件夹搬到别的机器上仍然能验。

### 校验

```bash
quickhash --check SHA256SUMS
```

```
a.txt: OK
b.txt: OK
c.txt: FAILED
  期望 8f4a3c...
  实际 1b2e9d...
d.txt: FAILED（文件不存在）

3 个通过，1 个失败
```

算法会从哈希串长度**自动推断**（32 位 md5、40 位 sha1、64 位 sha256、128 位 sha512），不用记。想强制指定就加 `-a`。

退出码：全部通过 `0`，有失败 `1`，参数/文件问题 `2`——可以直接接在脚本里：

```bash
quickhash --check SHA256SUMS && echo "镜像完好，开始安装"
```

## 参数

| 参数 | 说明 |
| --- | --- |
| `-a, --algo` | `md5` / `sha1` / `sha256` / `sha512` |
| `-r, --recursive` | 递归目录 |
| `-s, --save FILE` | 写成校验文件 |
| `-c, --check FILE` | 按校验文件验证 |
| `-q, --quiet` | 只输出哈希，不带路径 |

## 几个细节

- **大文件不吃内存**：1 MB 一块流式读取，算 50 GB 的镜像内存占用也就几 MB
- **递归时自动跳过垃圾目录**：`.git`、`node_modules`、`__pycache__`、`.venv` 不会混进校验文件
- **同一个文件给两次只算一次**：去重按真实路径，符号链接不会重复计算
- **兼容 `*filename` 写法**：coreutils 的二进制模式标记也能正确解析
- **读不了的文件不中断整批**：记一条错误继续往下走，最后退出码非 0

## 作为库调用

```python
from quickhash import core

print(core.hash_file("镜像.iso"))                    # sha256
core.write_checksums(["a.bin", "b.bin"], "SUMS.txt")
for r in core.verify("SUMS.txt"):
    print(r.name, r.status)
```

## 测试

```bash
python -m unittest discover -s tests -v
```

14 个用例，其中哈希正确性用**标准测试向量**（`sha256("abc")`、空文件的 sha256）核对，不是拿自己算的结果验自己。

## 许可

MIT License，详见 [LICENSE](LICENSE)。

---

<sub>English: QuickHash is a zero-dependency CLI to compute file digests, generate checksum files and verify downloads. Output is byte-compatible with coreutils `sha256sum`, so it interoperates with `SHA256SUMS` files published by Linux distros. Streams in 1 MB chunks, auto-detects the algorithm from digest length when verifying, shows a progress bar for files over 128 MB, and returns proper exit codes for scripting.</sub>
