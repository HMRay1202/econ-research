# GitHub 推送准备记录

核对日期：2026-09-02。本文件是待提交版本的检查与交接记录，不表示已经发布。

提交交接：用户随后授权停止后台并进行本地提交。提交前已确认 8000 端口无监听，
本项目 serve 和 Paddle worker 均已停止。本次提交包含下述 41 个文件，不执行 GitHub
推送。下文“尚未暂存/提交”的描述保留为此前准备阶段快照；实际提交 SHA 以
`git log -1 --oneline` 为准，远端发布须另行确认。

## Git 状态与范围

- 目标仓库：`origin` → `https://github.com/HMRay1202/econ-research.git`。
- 当前分支：`main`。本轮通过 `git ls-remote --heads origin main` 核对远端。
- 核对时本地 HEAD 和远端 main 均为 `58f8f1d5df0c99b2acde1e31d89063547441c33d`。
- 新功能和修复仍在工作区，尚未暂存、提交或推送；本轮未创建标签或 GitHub Release。
- 本轮最终清单为 26 个已跟踪文件修改、15 个新增文件，共 41 个待提交文件。
- 包版本仍为 `0.1.0`；没有为本次准备擅自指定新版本号。

同步的提交历史不等于全部修改已上传。正式提交时需要同时包含已有修改和下列新增文件，
不能只提交 README，也不能遗漏当前未跟踪的实现与测试。

## 本次变更摘要

1. **平台与运行库**：Windows/macOS 启动器使用统一硬件策略与安装检查。支持的 Windows
   NVIDIA 配置将 Torch CUDA 与 Paddle GPU 隔离在两个环境/进程中，避免 cuDNN DLL 冲突。
   CPU Windows 与 macOS 保留 CPU Paddle，macOS Torch 可使用 MPS。
2. **首次运行**：默认补齐公式库；检查只执行导入和小型运算，不实例化 OCR 模型。
   缺失模型在实际解析/识别时下载；已有模型缓存复用。`--without-formula` 只跳过库安装，
   若要关闭已有 OCR 功能需设置 `ECON_RESEARCH_PADDLE_FORMULA_OCR=false`。
3. **后台控制**：Windows 前台服务直接运行环境中的 Python，Ctrl+C 请求优雅退出。
   已有服务可选重启、停止、日志或退出；另有独立停止 CMD。备用停止入口核对进程与活动
   上传并要求确认，但属于终止操作，用户须先结束其他重解析/卡片/深读请求。
4. **论文删除**：受控目录内的 Windows 只读文件/目录可重试删除；不绕过其他锁或 ACL。
   文件清理完成后才删除数据库记录，失败返回 409，并在后台记录具体错误。
5. **公式质量与诊断**：规范化与置信度检查、逐次识别记录、失败裁剪图和新增只读 API；
   卡片正文共用安全 Markdown/KaTeX 渲染，无法渲染时显示未验证代码而非原始错误。
6. **中断恢复**：遗留 queued/running 上传标记 interrupted；未完成卡片生成标记失败，
   保留旧卡片，不自动重放计费请求。

## 新增文件不能遗漏

- `.gitattributes`、`stop-research.cmd`、`PROJECT_NARRATIVE.txt`。
- `scripts/runtime_policy.py`、`scripts/setup_runtime.py`、`scripts/stop-server.ps1`、
  `scripts/watch-server-logs.ps1`。
- `src/econ_research/parsing/paddle_process.py`、`paddle_worker.py`。
- `tests/test_launchers.py`、`test_paddle_process.py`、`test_runtime_policy.py`、
  `test_windows_cleanup.py`、`test_windows_server_control.py`。
- 本文件，以及 `git diff --name-only` 中已有源码、测试和文档修改。

## 验证记录

| 检查 | 本轮结果及边界 |
| --- | --- |
| Ruff | `ruff check .` 通过 |
| 离线测试 | Windows / econ-research / Python 3.11：107 passed，1 个依赖弃用警告 |
| Windows 删除 | 临时测试文件覆盖只读目录、裁剪图、PDF、Markdown、报告；没有删除真实论文 |
| 停止保护 | 测试覆盖目标进程、PID 变化、活动上传、取消、只检查；无全局 Python/taskkill 操作 |
| Git 差异 | `git diff --check` 通过；本轮未改业务代码或重启后台 |
| 文件安全 | 版本控制候选中未发现运行时数据/模型、超过 10 MiB 的文件或扫描规则匹配的密钥 |
| Git 忽略 | `.env`、数据库、模型、日志及 Python 缓存保持忽略；未使用强制添加 |
| macOS 启动文件 | 索引保留 `100755` 可执行模式，`.gitattributes` 指定 `.command` 为 LF、`.cmd` 为 CRLF |

测试警告来自 Starlette 对当前 `httpx` TestClient 适配方式的弃用提示，不是失败。
密钥扫描是启发式预检，不是绝对安全保证；暂存后仍需检查实际提交内容。

此前同机实测：RTX 5070 Ti Laptop GPU 上 Torch 2.9.1/cu130 与隔离 Paddle 3.3.1/cu130
运行成功。一次用户发起的合成 PDF 导入约 75 秒完成，保存 15 个文本块和 15 张卡片；
16 处公式中 15 处通过、1 处第 5 页低置信度公式在三次裁剪尝试后回退。导入成功不等于
全部公式正确。本轮仅复用该事实记录，没有为文档验证发起新的 LLM 调用。

## 未完成的跨平台与质量验证

- 本次修改尚未在原生 macOS、全新 CPU-only 环境或 CUDA 12.6 设备上完整安装验证。
  Windows 上的平台策略测试不能代替这些验证，也没有新的跨平台 CI 成功记录。
- 公式校验仍是启发式；浏览器级渲染回归、复杂公式和正文质量仍需核对原始 PDF。
- 睡眠/唤醒与原生解析器稳定性、刷新和批量上传体验仍见 [ROADMAP.md](../ROADMAP.md)。
- `formula-gpu` 是保留的旧 extra，不应在主 Windows 环境手动安装。
- 强制终止不保证优雅清理；并发任务启动存在检查时间差，优先使用服务原窗口 Ctrl+C。

## 数据与升级边界

不推送 PDF、数据库、解析文本、生成报告、裁剪图、模型权重、下载缓存、`.env` 或机器
专属解释器路径。新设备通过脚本安装环境、首次识别时下载模型，而不是复制本机环境。
`formula_attempts` 使用增量建表和索引；不迁移数据目录，不改写旧路径，不删除数据库。
旧论文不会自动重解析或重新生成卡片。启动服务时会按既有恢复逻辑更新遗留任务状态。
更新已部署的设备前先结束任务并停止旧服务，保留/备份原始资料和数据库，再更新代码、
执行对应启动器检查并重新启动。`/api/ui-version` 是界面版本标记，不是运行代码的 Git SHA，
不能仅凭标记相同认定旧进程已加载本次修改。

## 获准后执行的发布步骤

1. 再次核对 `git status --short --branch`、`git remote -v` 和远端 main；若远端前进，先审查
   差异，不覆盖远端、不强推、不重置现有工作区。
2. 按上面的文件范围显式暂存，检查 `git diff --cached --stat`、
   `git diff --cached --check` 和实际补丁，重新检查敏感内容与意外删除。
3. 建议提交说明：`feat: harden Windows GPU runtime and paper workflows`。
   提交后执行普通 `git push origin main`；未经明确要求不创建版本标签或 Release。
4. 用 `git ls-remote --heads origin main` 对比提交 SHA，确认上传成功，再更新发布状态。

文档入口：[README](../README.md)、[开发说明](../DEVELOPMENT.md)、
[架构](../ARCHITECTURE.md)、[交接状态](current-status.md)、[API 合约](api-contracts.md)。
