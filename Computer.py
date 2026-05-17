import serial
import json
import time
import requests

SERIAL_PORT = 'COM26'  # 🔑 請確保這是你目前的 COM 埠
BAUD_RATE = 115200
GEMINI_API_KEY = "AIzaSyC-8McGWqxCK0VEFm51-IX6hr2pHRQ6n6Y"

def ask_gemini_ai_native(json_data):
    # ✨ 關鍵修改：命令 Gemini 只能用小於 16 個字元的純英文消防指令回答（因為 LCD1602 的限制）
    prompt = f"You are a fire fighting robot. Based on this sensor data: {json_data}, give ONE short life-saving instruction in plain English. STRICT RULE: Must be under 16 characters total. Do not include punctuation."
    
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY.strip()}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        session = requests.Session()
        session.trust_env = False  # 忽略殘留的 proxy
        response = session.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            return ai_text.strip()
        else:
            return f"Error:{response.status_code}"
    except Exception as e:
        return f"Timeout/Error"

# 啟動主迴圈
last_ai_time = 0  
try:
    with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
        print("--- 消防雙向 AI 監控中 ---")
        ser.reset_input_buffer()
        
        while True:
            if ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                        
                    try:
                        data = json.loads(line)
                        if "sensors" in data and data["sensors"].get("fire_detected") == True:
                            current_time = time.time()
                            
                            if current_time - last_ai_time > 30: # 30秒防爆鎖
                                print(f"\n[🚨 偵測火災]: {line}")
                                
                                # 1. 獲取 AI 英文指令
                                ai_response = ask_gemini_ai_native(line)
                                print(f"== Gemini 導引方案 ==: {ai_response}")
                                
                                # ✨ 2. 關鍵動作：將 AI 指令加上換行符 \n，透過 Serial 傳回給 ESP32
                                # encode('utf-8') 會把字串轉為 byte 流送出
                                ser.write(f"{ai_response}\n".encode('utf-8'))
                                print("👉 已將指令成功回傳至 ESP32 LCD 顯示器")
                                
                                last_ai_time = current_time 
                            else:
                                print(".", end="", flush=True) 
                                
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    print(f"讀取錯誤: {e}")
            time.sleep(0.05)
except serial.SerialException as e:
    print(f"無法開啟序列埠: {e}")