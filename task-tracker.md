# busytag-llm-meter Task Tracker

> Single source of truth for outstanding work on this repo.
> 全域 milestone 同步到 `~/Darrell/daily/project-tracker.md`。

## 🔴 待完成

### Phase 1 — Core lift（**進行中**）
詳細 spec：`docs/phase-1-spec.md`

- [x] `busytag_meter/device/serial_io.py` — `BusytagDevice` class + flock + AT+UF/AT+SP ack + retry
- [x] `busytag_meter/device/discovery.py` — `find_device()` scan + AT ping
- [x] `busytag_meter/sources/base.py` — `UsageSource` ABC + `UsageSnapshot` dataclass
- [x] `busytag_meter/sources/_shared_state.py` — `read_state` / `write_state` + max() v2 消歧 + atomic write
- [x] `busytag_meter/sources/claude_code.py` — `ClaudeCodeSource` + `dump_from_stdin()`
- [x] `busytag_meter/sources/codex.py` — `CodexSource` + `poll_and_dump()` 讀 `~/.codex/sessions/**/rollout-*.jsonl`
- [x] `busytag_meter/display/renderer.py` — PIL 240×280 雙列 + stale 灰化
- [x] `busytag_meter/display/refresh.py` — `run_once` + `run_forever`
- [x] `busytag_meter/cli.py` — typer app（`daemon` / `refresh` / `status` / `poll-codex`）
- [x] `tests/test_shared_state.py` — max() v2 五個 case
- [x] `tests/test_codex_poll.py` — fixture-based rollout 解析
- [x] `tests/test_renderer.py` — PNG 產出驗證
- [x] `pip install -e .` 成功、`pytest` 過（13/13）、`python -m busytag_meter status` + `poll-codex` 驗證 OK（device 顯示需手動，需接實機）

### Phase 2 — Installer / Hooks / Doctor
（Phase 1 收尾後寫 `docs/phase-2-spec.md`）

- [ ] `installer/cron.py` — 寫入 / 移除 crontab entry（`crontab -l` 讀、append、`crontab -` 寫回）
- [ ] `hooks/settings_merger.py` 安全 merge `~/.claude/settings.json`
- [ ] `installer/doctor.py` 自我診斷 CLI
- [ ] `install.sh` shim（curl|bash 入口）
- [ ] `uninstall.sh`
- [ ] 字型 vendor 進 `assets/fonts/`

### Phase 3 — Polish + 公開化
- [ ] README demo GIF（裝置實拍）
- [ ] `docs/architecture.md` 補完
- [ ] `docs/adding-sources.md` 補完
- [ ] `docs/troubleshooting.md` 補完
- [ ] `.github/workflows/ci.yml` 真的跑 pytest
- [ ] private CLAUDE.md grep 一次確認無洩漏
- [ ] tag `v0.1.0-alpha`

### Phase 4 — PyPI + GitHub
- [ ] GitHub repo 建立、push main
- [ ] PyPI account / token 設定
- [ ] `python -m build && twine upload`
- [ ] 確認 `pipx install busytag-llm-meter` 從 PyPI 裝得到
- [ ] tag `v0.1.0` release notes

## 🟡 等外部 / 待確認

- [ ] Codex `notify` hook 與既有 `SkyComputerUseClient` 設定能否共存（Phase 2 才碰到，先 polling 不卡）
- [ ] PyPI 帳號 / API token 是否已有（Phase 4 才需要）
- [ ] GitHub repo 公開時間點（Phase 4 之前都不公開）

## 📋 後續方向（roadmap，非 v1）

- Homebrew tap（v1.1，需先 PyPI 站穩）
- Linux systemd 支援
- 多 source 動態切換（不只 Claude/Codex）：Aider / Cursor / Gemini CLI 等
- Web dashboard（看歷史用量曲線）
- Codex notify hook first-class 整合（即時 update，不依賴 polling）

## ✅ 已完成

| 日期 | 項目 | 備註 |
|------|------|------|
| 2026-05-13 | Phase 0：研究 + skeleton | Codex 訊號源確認、HTTP API 路線排除、PyPI 名字確認、repo skeleton commit `bd22053` |
| 2026-05-13 | Branch rename `master` → `main` | — |
| 2026-05-13 | PLAN.md / docs/phase-1-spec.md / task-tracker.md | 交接文件三件套 |
| 2026-05-13 | Phase 1 Core lift 完成 | 13 tests pass；`status` + `poll-codex` CLI 驗證 OK；device 顯示需手動接實機測 |

## 會議紀錄

無（單人專案）。
