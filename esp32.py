from machine import Pin, I2C, ADC
from lcd1602_i2c import LCD
import time
import ujson
import sys
import uselect  # ✨ 引入異步異步監聽庫

# 1. 硬體初始化
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=50000)
lcd = LCD(i2c, i2c_addr=0x27)
smoke_sensor = ADC(Pin(34))
flame_sensor = ADC(Pin(35))
smoke_sensor.atten(ADC.ATTN_11DB)
flame_sensor.atten(ADC.ATTN_11DB)
buzzer = Pin(25, Pin.OUT, value=1)
btn_up = Pin(19, Pin.IN, Pin.PULL_UP)

# 2. AI 特徵變數
history_smoke = [0] * 5
last_smoke = 0
reaction_factor = 0.85 

# 設定 sys.stdin 監聽器
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)

# --- 第一階段：環境動態校準 ---
lcd.clear()
f_list, s_list = [], []
for i in range(15, 0, -1):
    f_raw, s_raw = flame_sensor.read(), smoke_sensor.read()
    f_list.append(f_raw); s_list.append(s_raw)
    lcd.write(0, 0, "Calibrating:{:2d}s".format(i))
    lcd.write(0, 1, "F:{:4d} S:{:4d}".format(f_raw, s_raw))
    time.sleep(1)

f_threshold = sum(f_list)/len(f_list) - 1000
s_threshold = sum(s_list)/len(s_list) + 800

lcd.clear()
lcd.write(0, 0, "System Armed!")

# --- 第二階段：監控與 AI 聯動 ---
while True:
    try:
        s_val, f_val = smoke_sensor.read(), flame_sensor.read()
        
        # [邊緣運算] 計算 AI 特徵
        slope = s_val - last_smoke
        history_smoke.append(s_val); history_smoke.pop(0)
        pred_10s = history_smoke[-1] + (history_smoke[-1] - history_smoke[0])
        last_smoke = s_val
        
        # 判定是否異常
        is_danger = (f_val < f_threshold) or (s_val > s_threshold)

        if is_danger:
            ai_data = {
                "sensors": {
                    "smoke_raw": s_val,
                    "smoke_slope": slope,
                    "predicted_smoke_10s": pred_10s,
                    "fire_detected": f_val < f_threshold
                },
                "user_context": {"reaction_factor": reaction_factor}
            }
            print(ujson.dumps(ai_data))
            
            lcd.write(0, 0, "AI ANALYZING... ")
            lcd.write(0, 1, "S:{:4d} SL:{:3d}  ".format(s_val, slope))
            buzzer.value(0); time.sleep_ms(100); buzzer.value(1)
            
            if s_val > s_threshold + 500: # 本地強制警報
                lcd.write(0, 0, "!! FIRE ALERT !!")
                buzzer.value(0)
        else:
            buzzer.value(1)
            lcd.write(0, 0, "STATUS: SECURE  ")
            lcd.write(0, 1, "S:{:4d} F:{:4d}  ".format(s_val, f_val))
            print(ujson.dumps({"status": "safe", "s": s_val}))
            
        # ✨ 新增：檢查電腦端有沒有傳回 Gemini AI 的指令
        # timeout=50 代表只花 50 毫秒檢查，不影響火災感測器的每秒刷新
        if poll.poll(50): 
            ai_cmd = sys.stdin.readline().strip() # 讀取電腦丟進來的文字
            if ai_cmd:
                lcd.clear()
                # 第一行印出標題
                lcd.write(0, 0, "GEMINI COMMAND:") 
                # 第二行顯示 AI 的英文避難指令
                lcd.write(0, 1, ai_cmd[:16]) # 限制最多 16 個字元防爆行
                
                # 閃爍蜂鳴器提醒使用者看螢幕
                for _ in range(3):
                    buzzer.value(0); time.sleep_ms(50)
                    buzzer.value(1); time.sleep_ms(50)
                
                time.sleep(3) # 讓指令在螢幕上強制停留 3 秒

        if btn_up.value() == 0:
            lcd.clear(); lcd.write(0, 0, "USER RESET"); time.sleep(1)

        time.sleep(1.0) 
    except Exception as e:
        # 如果 LCD 離線則重新初始化
        lcd.__init__(i2c, i2c_addr=0x27)
