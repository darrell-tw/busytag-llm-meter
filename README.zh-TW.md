# busytag-llm-meter

English | [繁體中文](README.zh-TW.md)

**在桌上的 [Busy Tag](https://busytag.com) USB 裝置即時顯示你的 Claude Code 和 Codex 用量。**

![CI](https://github.com/darrell-tw/busytag-llm-meter/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: alpha](https://img.shields.io/badge/status-alpha-orange)

> 📸 Demo GIF 即將推出

---

## 硬體需求

一台 [Busy Tag](https://busytag.com) USB 裝置。它透過 USB CDC serial 溝通，接受 AT 指令 — macOS 和 Linux 不需要額外安裝驅動程式。

---

## 安裝

尚未發布到 PyPI，請從原始碼安裝：

```bash
git clone https://github.com/darrell-tw/busytag-llm-meter
cd busytag-llm-meter
pip install -e .
```

---

## 資料來源

| 來源 | 運作方式 | 需要 |
|------|---------|------|
| **Claude Code** | 讀取 Claude Code Stop hook 寫入的 `/tmp/busytag-meter-usage.json` | Claude Code CLI |
| **Codex** | 掃描 `~/.codex/sessions/**/rollout-*.jsonl` 取得最新 `token_count` 事件 | Codex CLI |

### 設定 Claude Code Hook

在 `~/.claude/settings.json` 加入以下設定：

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python -m busytag_meter dump-claude-stdin"
          }
        ]
      }
    ]
  }
}
```

驗證是否正常運作：

```bash
echo '{"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":9999999999}}}' \
  | python -m busytag_meter dump-claude-stdin
busytag-meter status
```

---

## 使用方式

```bash
busytag-meter status        # 顯示目前用量 JSON
busytag-meter poll-codex    # 手動拉取最新 Codex session 資料
busytag-meter refresh       # 渲染一次並推送到裝置
busytag-meter daemon        # 在前景執行定時刷新（每 120 秒）
```

背景自動執行（加入 crontab，每 2 分鐘執行一次）：

```bash
busytag-meter install       # 自動設定 cron 排程 + Claude Code hook
```

> ⚠️ `busytag-meter install` 尚未實作，詳見 [task-tracker.md](task-tracker.md)。

---

## 目前狀態

| 模組 | 狀態 |
|------|------|
| `sources/claude_code.py` | ✅ 讀取共享狀態，`dump_from_stdin()` 可用 |
| `sources/codex.py` | ✅ 掃描 `~/.codex/sessions/` JSONL |
| `device/` 序列埠驅動 | ✅ AT+UF / AT+SP / AT+SC，含 force-reload pivot |
| `display/renderer.py` | ✅ Pillow 240×280 PNG，雙 provider 版面 |
| `display/refresh.py` | ✅ hash 比對，內容未變則跳過上傳 |

---

## 架構

```
Claude Code Stop hook
      │  (stdin JSON 含 rate_limits)
      ▼
python -m busytag_meter dump-claude-stdin
      │  寫入 /tmp/busytag-meter-usage.json
      ▼
sources/claude_code.py ──┐
                          ├──► display/renderer.py ──► device/serial_io.py ──► Busy Tag
sources/codex.py ────────┘     (Pillow 240×280)         (AT 指令)
      ▲
~/.codex/sessions/**/rollout-*.jsonl
```

動手前必讀的設計決策：

- **單一寫者 + `resets_at` 優先消歧**：多個並行的 Claude Code session 各自帶著過期快照。判斷新舊要看 `resets_at`（block 時間），不是 `used_percentage` 的高低。邏輯在 `sources/_shared_state.py`。
- **Force-reload pivot**：Busy Tag firmware 的 `AT+SP=相同檔名` 會靜默 no-op，不更新畫面。驅動程式改用輪替檔名的方式繞過。完整陷阱清單在 `docs/serial-survival-guide.md`。
- **flock 鎖 serial port**：同一時間只有一個 process 持有 `/tmp/busytag-serial.lock`。

檔案結構：

```
busytag_meter/
  cli.py              — typer CLI 進入點
  sources/
    _shared_state.py  — /tmp/busytag-meter-usage.json 的 atomic 讀寫
    base.py           — UsageSource ABC + UsageSnapshot dataclass
    claude_code.py    — ClaudeCodeSource + dump_from_stdin()
    codex.py          — CodexSource + poll_and_dump()
  display/
    renderer.py       — render_frame(claude, codex) → PNG bytes
    refresh.py        — run_once() / run_forever() 主流程
  device/
    discovery.py      — find_device() → serial port 路徑
    serial_io.py      — BusytagDevice context manager（AT 指令封裝）
  hooks/              — 尚未實作（未來存放 hook 腳本）
  installer/          — 尚未實作（未來：cron + settings.json 合併）
docs/
  serial-survival-guide.md  — AT 協議陷阱清單
  architecture.md           — 元件概覽
  adding-sources.md         — 如何新增資料來源
```

---

## 給 AI 助理

如果你是正在幫忙實作缺少部分的 AI 助理，請先讀這一節。

**已實作且通過測試：**
- `sources/claude_code.py` — `ClaudeCodeSource.read()` 和 `dump_from_stdin()`
- `sources/codex.py` — `CodexSource.read()` 和 `poll_and_dump()`
- `sources/_shared_state.py` — `read_state()` / `write_state()`，含 atomic tmp+mv 和 `resets_at` 優先消歧
- `device/serial_io.py` — AT+UF 上傳、AT+SP 切換顯示、AT+SC LED、force-reload pivot
- `display/renderer.py` — 雙 provider 240×280 Pillow 渲染
- `display/refresh.py` — hash 比對迴圈

**待實作（依優先序）：**

1. **`installer/cron.py`** — 讀取現有 crontab（`crontab -l`），追加 `*/2 * * * * /絕對路徑/busytag-meter refresh`，寫回（`crontab -`）。必須冪等，不可重複新增。
2. **`installer/settings_merger.py`** — 安全合併 Stop hook 進 `~/.claude/settings.json`，不破壞既有 hook。用 `json.load` / `json.dump`，禁止 regex。
3. **`cli.py` `install` 指令** — 呼叫兩個 installer，逐步印出 ✅/❌。
4. **`hooks/` 獨立腳本** — 在 `pip install` 之前也能用的零依賴 hook 腳本。

**限制條件：**
- 不可破壞 `_shared_state.py` 的 `resets_at` 優先消歧邏輯。
- Cron entry 必須使用 `shutil.which("busytag-meter")` 取得的絕對路徑。
- 所有新程式碼必須通過 `pytest tests/ -v`，Python 3.10+。
- 修改 `device/` 之前必須先讀 `docs/serial-survival-guide.md`。

---

## 致謝

- [Busy Tag USB CDC command reference](https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide)
- [busytag_tool](https://github.com/acoster/busytag_tool) — 社群 Python 驅動，最初靈感來源
- [busylight](https://github.com/JnyJny/busylight) — 多裝置 USB 燈具函式庫

## 授權

MIT © 2026 Darrell Wang
