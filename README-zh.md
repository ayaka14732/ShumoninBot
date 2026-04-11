# Shumonin Bot

**Shumonin Bot** 是一個 Telegram 群組管理機器人，利用 AI（透過 OpenRouter 接入 Qwen3.5-Flash）透過多輪對話來驗證新成員。它能有效防止垃圾訊息、嚴格執行入群標準，並為群組管理員提供流暢的設定體驗。

## 核心功能

- **AI 驅動驗證**：根據自訂問題與標準，與新成員進行多輪對話面試。
- **名稱預檢**：在驗證開始前，自動踢出顯示名稱包含廣告、色情或詐騙特徵的用戶。
- **垃圾訊息舉報**：用戶可回覆訊息並輸入 `/report`，交由 AI 靜默分析並刪除垃圾訊息，若確認為違規將自動封禁發送者。
- **引導式管理員設定**：提供簡便的 `/setup` 指令，可用自然語言配置驗證規則。
- **安全防護機制**：具備頻率限制、最大回答長度限制、超時輪詢與封禁閾值等防護。

## 專案架構

```
shumonin-bot/
├── main.py                  # 程式入口，初始化 Bot 與處理器
├── config.py                # 環境變數與靜態設定
├── README.md                # 英文說明文件
├── README.zh.md             # 中文說明文件
│
├── core/                    # 核心業務邏輯
│   ├── actions.py           # Telegram API 封裝 (restrict/kick/ban)
│   ├── scheduler.py         # 背景超時輪詢任務
│   └── verifier.py          # AI 整合 (OpenRouter API 呼叫)
│
├── db/                      # 資料庫層 (SQLite)
│   ├── database.py          # 連線與資料表建立
│   └── queries.py           # CRUD 操作
│
├── handlers/                # Telegram 事件處理器
│   ├── commands.py          # 管理員指令 (/setup, /settings 等)
│   ├── join.py              # new_chat_members 事件
│   ├── leave.py             # chat_member 事件 (離開/被踢)
│   ├── message.py           # 群組訊息 (回答與設定輸入)
│   ├── report.py            # /report 指令
│   └── shared.py            # 共用的成功/失敗處理流程
│
└── prompts/                 # AI 系統提示詞
    ├── name_check.txt
    ├── spam_check.txt
    └── verification.txt
```

## 系統需求

- Python 3.11+
- `python-telegram-bot`
- `openai` (用於相容 OpenRouter)
- `python-dotenv`

## 安裝與執行

1. 在專案根目錄建立 `.env` 檔案：
   ```env
   TELEGRAM_BOT_TOKEN=你的_telegram_bot_token
   OPENROUTER_API_KEY=你的_openrouter_api_key
   ALLOWED_CHAT_IDS=-100123456789,-100987654321
   DB_PATH=bot.db
   ```

2. 安裝相依套件：
   ```bash
   pip install python-telegram-bot openai python-dotenv
   ```

3. 啟動機器人：
   ```bash
   python main.py
   ```

## 管理員指令

- `/setup` - 開始引導式設定流程。
- `/setquestion` - 更新驗證問題。
- `/setexpected` - 更新判分標準。
- `/settimeout` - 更新超時時間。
- `/settings` - 查看當前群組設定。
- `/unban <user_id>` - 重置機器人端的封禁與失敗次數記錄。
- `/status` - 檢查機器人權限狀態。
- `/cancel` - 取消當前的設定流程。
- `/help` - 顯示所有指令說明。
