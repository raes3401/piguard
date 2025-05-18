# -*- coding: utf-8 -*-
import RPi.GPIO as GPIO
import cv2
import time
import os
import requests
import threading
from datetime import datetime
import mediapipe as mp
import json
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 只顯示錯誤（Error），不顯示警告與 Info

# ====== 從 config.json 載入設定 ======
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    bot_token = config.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.get("TELEGRAM_CHAT_ID")

# ====== 設定區 ======
SENSOR_PIN = 17
base_folder = '/home/kingc/Desktop/piguard'
gdrive_folder = 'PiGuard_Backup'
# =====================

# 初始化 GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# 建立資料夾
if not os.path.exists(base_folder):
    os.makedirs(base_folder)

# 開啟攝影機
camera = cv2.VideoCapture(0)
time.sleep(3)

# 初始化 Mediapipe
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

# 狀態控制
motion_active = False
detection_enabled = False
current_folder = None
send_count = 0
upload_threads = []
upload_queue = []

# ===== 網路檢查功能 =====
def is_connected():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except requests.RequestException:
        return False

# ===== Telegram 功能 =====
def send_telegram_message(text):
    if is_connected():
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {'chat_id': chat_id, 'text': text}
        try:
            requests.post(url, data=data)
        except:
            print("⚠️ 發送 Telegram 失敗")
    else:
        print("⚠️ 無法發送 Telegram（斷網）")

def send_telegram_photo(photo_path, caption):
    if is_connected():
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        try:
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {'chat_id': chat_id, 'caption': caption}
                requests.post(url, files=files, data=data)
        except:
            print("⚠️ 上傳 Telegram 照片失敗")
    else:
        print("⚠️ 無法上傳 Telegram 照片（斷網）")

# ===== AI 判斷功能 =====
def detect_person_ai(frame):
    results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return bool(results.pose_landmarks)

# ===== Google Drive 上傳 =====
def upload_folder(folder_path):
    if folder_path and os.path.exists(folder_path):
        folder_name = os.path.basename(folder_path)
        if is_connected():
            print("☁️ 網路可用，正在上傳至 Google Drive...")
            os.system(f"rclone move '{folder_path}' 'PiGuard:{gdrive_folder}/{folder_name}/' --delete-empty-src-dirs")
            print("✅ 資料夾已同步並刪除本地")
        else:
            print("⚠️ 網路不可用，加入排程等待上傳")
            upload_queue.append(folder_path)

# ===== 網路恢復監控（補上傳 + 通知）=====
def network_monitor():
    while True:
        if is_connected() and upload_queue:
            print("🌐 網路恢復，開始上傳排程資料...")
            for path in upload_queue[:]:
                folder_time = os.path.basename(path).split("_")[-1]
                send_telegram_message(f'📶 網路恢復，自動上傳：{folder_time}')
                upload_folder(path)
                upload_queue.remove(path)
        time.sleep(10)

# ===== 拍照主程式（每 5 秒拍照 + AI 辨識）=====
def photo_loop():
    global motion_active, current_folder, send_count
    while True:
        if motion_active and detection_enabled:
            ret, frame = camera.read()
            if ret and current_folder:
                photo_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_name = f"{photo_time}.jpg"
                photo_path = os.path.join(current_folder, photo_name)
                cv2.imwrite(photo_path, frame)
                print(f"📷 拍攝並保存：{photo_path}")

                if detect_person_ai(frame):
                    print("✅ AI 判定畫面中有人")
                else:
                    print("❌ AI 判定畫面無人，無效照片")

                if send_count < 3:
                    send_telegram_photo(photo_path, f'🚨 PiGuard偵測到入侵！時間：{photo_time}')
                    send_count += 1
                elif send_count == 3:
                    send_telegram_message('📡 正持續偵測中（不再發送照片）')
                    send_count += 1
            time.sleep(5)
        else:
            time.sleep(1)

# ===== 人體偵測主程式（每 2.5 秒檢查 PIR）=====
def detect_motion():
    global motion_active, current_folder, send_count

    try:
        while True:
            if detection_enabled:
                motion_detected = GPIO.input(SENSOR_PIN)
                print("偵測輸出：", motion_detected)

                if motion_detected == 1 and not motion_active:
                    print("📡 PIR 偵測到，啟動 AI 確認")
                    ret, frame = camera.read()
                    if not ret:
                        print("⚠️ 相機讀取失敗")
                        continue

                    if detect_person_ai(frame):
                        print("🔴 AI 確認畫面中有人，啟動偵測模式")
                        motion_active = True
                        send_count = 0
                        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                        folder_name = f"入侵偵測_{current_time}"
                        current_folder = os.path.join(base_folder, folder_name)
                        os.makedirs(current_folder)
                        print(f"🚨 建立新資料夾：{current_folder}")
                    else:
                        print("⚪ AI 判定畫面無人，忽略此次觸發")

                elif motion_active and motion_detected == 0:
                    print("🛑 PIR 靜止，啟動 AI 離開確認")
                    ret, frame = camera.read()
                    if ret and not detect_person_ai(frame):
                        print("✅ AI 判定人已離開，結束偵測")
                        send_telegram_message('✅ 訊號已消失，偵測結束')
                        if current_folder:
                            t = threading.Thread(target=upload_folder, args=(current_folder,))
                            t.start()
                            upload_threads.append(t)
                        motion_active = False
                        send_count = 0
                        current_folder = None
            time.sleep(2.5)
    except KeyboardInterrupt:
        print("🛑 手動停止程式")
    finally:
        camera.release()
        GPIO.cleanup()
        print("✅ GPIO 與相機已釋放")

# ===== Telegram 指令監聽器 =====
def telegram_listener():
    global detection_enabled
    last_update_id = None
    try:
        while True:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            if last_update_id:
                url += f"?offset={last_update_id + 1}"
            try:
                response = requests.get(url)
                updates = response.json()
                if "result" in updates:
                    for update in updates["result"]:
                        last_update_id = update["update_id"]
                        if "message" in update:
                            text = update["message"].get("text", "").lower()
                            if text == "/start":
                                detection_enabled = True
                                send_telegram_message("🟢 PiGuard 偵測已啟動")
                            elif text == "/stop":
                                detection_enabled = False
                                send_telegram_message("🛑 PiGuard 偵測已停止")
            except:
                print("⚠️ 無法連接 Telegram API")
            time.sleep(2)
    except KeyboardInterrupt:
        pass

# ===== 主程式入口 =====
if __name__ == "__main__":
    if is_connected():
        print("🌐 已連接網路")
    else:
        print("⚠️ 未連接網路，將暫存資料至本地")

    threading.Thread(target=detect_motion).start()
    threading.Thread(target=photo_loop).start()
    threading.Thread(target=telegram_listener).start()
    threading.Thread(target=network_monitor).start()
