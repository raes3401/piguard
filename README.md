Raspberry Pi AI 保全系統
一個基於 Raspberry Pi 的智慧保全系統，結合 PIR 感測器、攝影機及 Mediapipe AI 人體偵測模型，實現自動偵測人體入侵，並透過 Telegram 即時警報及 Google Drive 雲端備份圖片。

功能簡介
PIR 動態偵測：感測環境是否有人體移動。

AI 影像辨識：利用 Mediapipe 判斷畫面中是否有人，減少誤報。

即時警報：偵測到入侵時，前 3 張照片即時透過 Telegram 傳送通知與圖片。

雲端備份：所有偵測圖片會同步上傳到 Google Drive，並在本地刪除。

離線緩存：若無網路，將照片暫存本地，連線恢復後自動備份。

Telegram 指令控制：可透過 /start 啟動與 /stop 停止偵測。

硬體需求
Raspberry Pi 5 (4GB 版本)

PIR 感測器 (HC-SR501)

USB 攝影機 (例如羅技 C310)

網路連線（Wi-Fi 或有線）

microSD 卡（安裝系統與存放程式與圖片）

軟體需求
Raspberry Pi OS (建議最新版 64-bit)

Python 3.11+

相關 Python 套件：

opencv-python

mediapipe

RPi.GPIO

requests

rclone：用於與 Google Drive 同步

Telegram Bot（需自行申請）

安裝與設定步驟
1. 安裝 Python 套件
bash
複製
sudo apt update
sudo apt install python3-pip
pip3 install opencv-python mediapipe RPi.GPIO requests
2. 安裝 rclone 並配置 Google Drive
bash
複製
sudo apt install rclone
rclone config
請依指示建立名為 PiGuard 的 Google Drive 遠端。
確保你的 Google Drive 資料夾名稱為 PiGuard_Backup 或自行調整程式中 gdrive_folder 參數。

3. 申請 Telegram Bot 並取得 bot_token 與 chat_id
打開 Telegram 搜尋 BotFather，依指示建立 Bot。

取得 bot_token（類似 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ）。

將 Bot 加入目標聊天群組或使用私人聊天，取得 chat_id（可用 API 查詢或其他工具）。

4. 配置程式碼參數
編輯 main.py，更新以下參數：

python
複製
SENSOR_PIN = 17  # PIR 感測器連接的 GPIO 腳位
base_folder = '/home/pi/piguard'  # 照片本地存放路徑
bot_token = '你的Telegram Bot Token'
chat_id = '你的Telegram Chat ID'
gdrive_folder = 'PiGuard_Backup'  # Google Drive 同步資料夾名稱
5. 執行程式
bash
複製
python3 main.py
開啟 Telegram，輸入指令：

/start 開啟偵測功能

/stop 關閉偵測功能

程式架構說明
detect_motion()：2.5 秒讀取 PIR 感測器，PIR 訊號觸發時用 AI 確認有人才啟動偵測。

photo_loop()：每 5 秒拍照，透過 AI 判斷照片是否有人，前 3 張照片會傳送 Telegram。

upload_folder()：事件結束後自動將資料夾同步到 Google Drive 並刪除本地檔案。

telegram_listener()：輪詢 Telegram 指令，控制偵測啟停。
