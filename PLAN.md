# busytag-llm-meter — Build Plan

> 高層 4-phase 規劃。Phase 內細節見 `docs/phase-N-spec.md`。本檔不重述 CLAUDE.md / serial-survival-guide.md / Subagent 研究結論，只列「該做什麼、誰先做、判準」。

## 專案定位

**The first AI usage meter for Busy Tag.** macOS only, Python, MIT, public GitHub.

差異化護城河（不能被輕易複製的部分）：
- `docs/serial-survival-guide.md`（已寫好）— 整個 Busy Tag 生態系第一份實戰文件
- `flock + single-writer + max(resets_at, used)` 三件套 multi-writer 安全機制（從私有專案四輪反面教材中蒸餾）
- Codex first-class 支援（讀 `~/.codex/sessions/**/rollout-*.jsonl`）

## 範圍邊界（不做的事）

- ❌ 不支援其他廠商裝置（busylight 已佔 324★，不重造）
- ❌ 不走 Local Server HTTP API（已驗證：與 USB serial 硬體互斥、無切顯 endpoint）
- ❌ 不做 .NET / C# 版本（社群 Python-first）
- ❌ 不做 Windows / Linux（v1 macOS only，launchd）
- ❌ 不重寫 AT 指令參考（連結 Luxafor 官方）
- ❌ 不在 v1 加 Homebrew tap

## Phase 摘要

| Phase | 目的 | 預估 | 輸出判準 |
|-------|------|------|----------|
| **0** | 研究 + skeleton | 0.5d | ✅ 已完成（commit `bd22053`） |
| **1** | Core lift：把 `~/.claude/hooks/` + `~/Darrell/code/busytag/` 既有邏輯重構進 package | 1-1.5d | `python -m busytag_meter daemon` 跑通，device 顯示 Claude + Codex 雙列 |
| **2** | Installer / Hooks / Doctor | 1-1.5d | `pipx install -e . && busytag-meter init` 在乾淨環境零互動裝完、launchd 接管 |
| **3** | Polish + 公開化 | 0.5d | README demo GIF、CI 過、`docs/` 完整、第一個 release tag `v0.1.0` |
| **4** | PyPI 上架 + GitHub 公開 | 0.25d | `pipx install busytag-llm-meter` 從 PyPI 裝得到 |

## 各 Phase 詳細 spec

- `docs/phase-1-spec.md`（**已寫好，可交接**）
- `docs/phase-2-spec.md`（Phase 1 收尾後產出）
- `docs/phase-3-spec.md`（同上）
- `docs/phase-4-spec.md`（同上）

## 核心架構決策（已定案）

| 決策 | 結論 | 依據 |
|------|------|------|
| 訊號源 — Claude Code | Stop hook stdin `rate_limits`（後端真值） | 私有 CLAUDE.md 已驗證 |
| 訊號源 — Codex | `~/.codex/sessions/**/rollout-*.jsonl` 中 `token_count.rate_limits`（polling 60s） | Phase 0 Subagent 1 實測，有 primary(5h) + secondary(weekly) |
| 共用狀態檔 | `/tmp/busytag-meter-usage.json`，schema `{source: {primary, secondary, ts}}` | 與私有 `/tmp/claude-rate-limits.json` **不同路徑**，避免互相干擾 |
| 寫入互斥 | `resets_at` 較舊→跳過；相同→`used` 較小跳過；新→寫 | 私有專案四輪反面教材 |
| Serial 互斥 | `/tmp/busytag-meter-serial.lock` flock，single-writer policy | 同上 |
| Device discovery | `/dev/cu.usbmodem*` + `AT` ping 驗證；多支時報錯讓使用者指定 | — |
| 字型 | 自帶 Noto Sans CJK subset 在 `busytag_meter/assets/fonts/` | 不依賴 STHeiti（macOS 系統字型不可攜） |
| 安裝方式 | `pipx install` 為主、`curl\|bash` shim 為次 | Phase 0 Subagent 2 ecosystem 分析 |
| 設定路徑 | `~/.config/busytag-llm-meter/config.toml`（XDG） | 對齊 busytag_tool |
| Branch | `main` | 已 rename |

## 進度追蹤

見 `task-tracker.md`。

## 給下個 sonnet session 的接手 prompt

直接複製這段貼到 fresh Claude Code session（cwd: `~/Darrell/code/busytag-llm-meter/`）：

```
接手 busytag-llm-meter Phase 1。讀以下順序：
1. PLAN.md（總覽 + 邊界）
2. docs/phase-1-spec.md（這次要做的事）
3. docs/serial-survival-guide.md（AT 協定踩坑，動 device/ 前必讀）
4. task-tracker.md（看目前進度）

參考檔（不要動）：
- ~/Darrell/code/busytag/CLAUDE.md（私有踩坑紀錄）
- ~/.claude/hooks/dump-rate-limits.py（既有 writer 邏輯來源）

Phase 1 範圍見 docs/phase-1-spec.md「Deliverables」section。完成判準見「Done when」。
動工前先把 task-tracker.md 的 Phase 1 待辦轉成 in_progress；完成後標 done 並 commit。
不要 push 到 GitHub（沒有 remote），不要動 ~/.claude/ 或私有 busytag/ 目錄。
```
