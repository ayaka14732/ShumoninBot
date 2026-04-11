# Shumonin Bot

**Shumonin Bot** 是一個 Telegram 群組管理機器人，利用 AI 透過多輪對話來驗證新成員。它能有效防止垃圾訊息、嚴格執行入群標準，並為群組管理員提供流暢的設定體驗。

## 核心功能

- **AI 驅動驗證**：根據自訂問題與標準，與新成員進行多輪對話面試。
- **供應商自動 Fallback**：AI 呼叫透過可設定的模型鏈（`core/ai_models.py`）依序嘗試，某個供應商失敗時自動切換至下一個。
- **名稱預檢**：在驗證開始前，自動踢出顯示名稱包含廣告、色情或詐騙特徵的用戶。
- **垃圾訊息舉報**：用戶可回覆任意訊息並輸入 `/report`，交由 AI 靜默分析；確認為垃圾訊息則刪除並封禁發送者。試圖舉報管理員時，舉報訊息本身會被靜默刪除。
- **引導式管理員設定**：提供簡便的 `/setup` 指令，可用自然語言配置驗證規則。
- **安全防護機制**：具備頻率限制、最大回答長度限制、超時輪詢與封禁閾值等防護。

## 系統需求

- Python 3.11+
- `python-telegram-bot`
- `openai` (用於相容 OpenRouter)
- `python-dotenv`

## BotFather 設定

將機器人加入群組前，必須先關閉隱私模式，讓機器人能讀取所有訊息：

1. 在 Telegram 開啟 [@BotFather](https://t.me/BotFather)。
2. 發送 `/mybots`，選擇你的機器人。
3. 進入 **Bot Settings** > **Group Privacy** > **Turn off**。

若未完成此步驟，機器人只能收到直接提及它的訊息，將無法正常運作。

## 安裝與執行

1. 在專案根目錄建立 `.env` 檔案：
   ```env
   TELEGRAM_BOT_TOKEN=你的_telegram_bot_token
   OPENROUTER_API_KEY=你的_openrouter_api_key
   OPENAI_API_KEY=你的_openai_api_key   # 選填，作為備用供應商
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
