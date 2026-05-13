# Phase 1 Spec — Core lift

> 把 `~/.claude/hooks/` 與 `~/Darrell/code/busytag/` 的既有運行邏輯，重構成 package 內可發佈的乾淨模組。私有 CLAUDE.md 與 `docs/serial-survival-guide.md` 已記載所有踩坑與協定細節，本檔不重述。

## Scope

Phase 1 只做 **lift + 兩個 source + daemon 跑通**。不做 installer、不做 hook 註冊、不做 doctor、不出包。

## Deliverables

### 1. `busytag_meter/device/`

| 檔案 | 內容 |
|------|------|
| `serial_io.py` | `BusytagDevice` class：`__init__(port)`、context manager（`__enter__` 取 flock、`__exit__` 釋放）、`upload(filename, png_bytes)`（完整 `AT+UF` ack + retry once on ack drop）、`show(filename)`（force-reload pivot + 等 `+evn:SP` ack）、`ping()`（送 `AT`、確認 `OK`） |
| `discovery.py` | `find_device() -> str`：scan `/dev/cu.usbmodem*`、對每個 candidate 做 `AT` ping、回第一個有回應的；多支或零支時 raise `DeviceNotFound` 帶清楚訊息 |
| `__init__.py` | re-export `BusytagDevice`、`find_device`、`DeviceNotFound` |

**flock 路徑**：`/tmp/busytag-meter-serial.lock`（**不要**用私有 setup 的 `/tmp/busytag-serial.lock`，避免新舊兩套互鎖）

**ack timeout**：upload 8s、show 3s（與私有 setup 對齊）

### 2. `busytag_meter/sources/`

| 檔案 | 內容 |
|------|------|
| `base.py` | `UsageSource` ABC：`name: str`、`read() -> Optional[UsageSnapshot]`、`stale_after_seconds() -> int`。`UsageSnapshot` dataclass：`source`、`primary_used_pct`、`primary_resets_at`、`secondary_used_pct`（可選）、`secondary_resets_at`（可選）、`plan_type`（可選）、`ts` |
| `claude_code.py` | `ClaudeCodeSource(UsageSource)`：從 `/tmp/busytag-meter-usage.json` 讀 `claude_code` key；另含 module-level function `dump_from_stdin()` 供 Phase 2 的 Stop hook 呼叫 |
| `codex.py` | `CodexSource(UsageSource)`：同上讀法；另含 `poll_and_dump()`：掃 `~/.codex/sessions/**/rollout-*.jsonl`（最新 3 個 by mtime）、找最新 `token_count.rate_limits`、消歧後寫 `/tmp/busytag-meter-usage.json` 的 `codex` key |
| `_shared_state.py` | `read_state() / write_state(source_name, snapshot)`：負責讀寫共用 JSON、執行 max() v2 消歧（`resets_at` 較舊跳過、相同則 `used` 較小跳過、新則寫）、atomic write via tmp+rename |
| `__init__.py` | re-export `UsageSource`、`UsageSnapshot`、`ClaudeCodeSource`、`CodexSource` |

**共用 state schema**：
```json
{
  "claude_code": { "primary": {"used_percent": 28, "resets_at": 1779000000}, "secondary": null, "plan_type": "max", "ts": 1778950000 },
  "codex":       { "primary": {"used_percent": 30, "resets_at": 1778597731}, "secondary": {"used_percent": 5, "resets_at": 1779174459}, "plan_type": "plus", "ts": 1778950500 }
}
```

### 3. `busytag_meter/display/`

| 檔案 | 內容 |
|------|------|
| `renderer.py` | `render(sources: list[UsageSnapshot \| None], stale_marker: dict[str, int]) -> bytes`（回 PNG bytes）。240×280 canvas、深色背景、每個 source 一列（label + 進度條 + %）、stale 時轉灰並標 `~Nm ago` |
| `refresh.py` | `run_once(device, sources)`：呼叫各 source `.read()` → 過 stale 判定 → render → device.upload + device.show；`run_forever(interval=120)`：迴圈呼叫 `run_once` |
| `assets/` | `default.png`（裝置 idle 時顯示）、`fonts/` 放 Noto Sans CJK subset（Phase 1 可暫用 system font，**留 TODO 註解**） |

**檔案命名 convention**：upload 上去叫 `usage.png`，force-reload pivot 用 `default.png`。

### 4. `busytag_meter/cli.py`

從 stub 升級成 typer app：

```python
import typer
app = typer.Typer()

@app.command()
def daemon(interval: int = 120):
    """Run the refresh loop in foreground."""
    # find device → loop refresh.run_forever
    ...

@app.command()
def refresh():
    """One-shot refresh, for testing."""
    ...

@app.command()
def status():
    """Print current shared state JSON."""
    ...

@app.command()
def poll_codex():
    """Poll latest Codex rollout JSONL and dump to shared state. For launchd cron-like trigger."""
    # codex.poll_and_dump()
    ...

def main():
    app()
```

Phase 2 會加 `install` / `uninstall` / `doctor` / `dump-claude-stdin`，**Phase 1 不做**。

### 5. Tests

`tests/test_shared_state.py`：max() v2 消歧的 5 個 case 都要過：
1. 空檔案，寫新值 → 寫進去
2. 舊值 `resets_at` 較舊 → 新值覆蓋（不論 used 大小）
3. 舊值 `resets_at` 較新 → 不覆蓋
4. 同 `resets_at`，新值 `used` 較大 → 覆蓋
5. 同 `resets_at`，新值 `used` 較小 → 不覆蓋

`tests/test_codex_poll.py`：餵一個 fixture rollout JSONL，確認抽出 `rate_limits` 正確（用 `~/.codex/` 真檔複製一份脫敏進 `tests/fixtures/`）。

`tests/test_renderer.py`：餵兩個 snapshot 與 stale marker，render 不 raise + 出來是 valid PNG（用 PIL load 回來驗證）。

不測 serial（需要實機）— Phase 2 doctor 才做 integration test。

## Done when

- [ ] `pip install -e .` 成功
- [ ] `python -m busytag_meter daemon` 跑起來，device 顯示 Claude + Codex 雙列（**需手動準備：跑一輪 Claude Code 對話讓 stdin 落地、開過 Codex session**）
- [ ] `pytest` 通過（至少上述 3 個測試檔）
- [ ] `python -m busytag_meter status` 印出當下 shared state
- [ ] `python -m busytag_meter poll-codex` 跑完後 status 看得到 codex 資料更新
- [ ] task-tracker.md 內 Phase 1 全部打勾
- [ ] commit 訊息 `feat: phase 1 core lift`

## 不做的事（Phase 2+）

| 不做 | 為何不做 | 在哪 phase 做 |
|------|----------|---------------|
| `busytag-meter install` / launchd plist 產生 | Phase 1 用 foreground daemon 驗證即可 | Phase 2 |
| Claude Code Stop hook 寫進 `~/.claude/settings.json` | 同上，先靠 `python -m busytag_meter daemon` 跑 | Phase 2 |
| Codex notify hook 註冊 | polling 60s 就夠 | Phase 2 或 3 |
| `doctor` 子命令 | Phase 1 先靠 `status` + 手動驗 | Phase 2 |
| 字型 vendor 進 repo | Phase 1 用 system font + TODO | Phase 2 開始公開化前處理 |
| PyPI 上架 | Phase 4 | Phase 4 |

## 參考檔對照

| 要做的事 | 參考既有實作 |
|----------|--------------|
| `device/serial_io.py` 的 AT 協定 | `~/Darrell/code/busytag/usage_display.py`（如不存在於該目錄，搜 `~/.claude/hooks/` 與 launchd plist 內 `ProgramArguments` 指向的 .py） |
| `sources/claude_code.py` 的 max() v2 邏輯 | `~/.claude/hooks/dump-rate-limits.py` |
| `sources/codex.py` 的 rollout JSONL 解析 | PLAN.md「核心架構決策」表 + 私有 CLAUDE.md 沒寫過此邏輯（Phase 0 新研究結果）|
| 所有 AT trap 解法 | `docs/serial-survival-guide.md`（**本 repo 內，公開版**） |

## 風險 / 注意

1. **不要動 `~/.claude/hooks/` 或 `~/Library/LaunchAgents/`** — 私有 setup 仍在跑、Phase 1 不取代它，兩套並存（不同 lock path、不同 state file path）
2. **不要 push 到 GitHub** — Phase 4 才上架。動完 commit 到本地 `main` 就好
3. **找不到 device 時要清楚 raise**，不要 silently 跑空迴圈
4. **render 字型 fallback**：找不到 STHeiti 就用 `ImageFont.load_default()` 並 log warning，**不要 raise**（讓 daemon 在沒中文字型的環境也能跑）
