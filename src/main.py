from gpiozero import Button, OutputDevice
from time import sleep
import os
import threading
import time
import firebase_admin
from firebase_admin import credentials, db

# ==============================
# Firebase 설정
# ==============================
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://YOUR_PROJECT_ID-default-rtdb.asia-southeast1.firebasedatabase.app/"
)
STAND_ID = os.getenv("STAND_ID", "stand_1")

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred, {
    "databaseURL": DATABASE_URL
})

stand_ref = db.reference(f"umbrella_stands/umbrellaStands/{STAND_ID}")
rental_request_ref = db.reference("umbrella_stands/rental_request/space_id")

# ==============================
# GPIO 핀 설정
# ==============================
solenoids = {
    1: OutputDevice(17),
    2: OutputDevice(18),
    3: OutputDevice(5),
    4: OutputDevice(6),
}

buttons = {
    1: Button(22),
    2: Button(23),
    3: Button(19),
    4: Button(24),
}

fans = [OutputDevice(25), OutputDevice(26)]

# ==============================
# 상태 변수
# D: 건조 완료/대여 가능, W: 건조 중, N: 비어 있음
# ==============================
R_states = {"R1": "D", "R2": "D", "R3": "D", "R4": "D"}
timers = {"timer1": 5, "timer2": 5, "timer3": 5, "timer4": 5}
timer_threads = {}
active_timers = {"timer1": False, "timer2": False, "timer3": False, "timer4": False}
fan_status = False
timer_lock = threading.Lock()


def update_firebase_status():
    # 현재 보관함 상태를 Firebase Realtime Database에 반영합니다.
    spaces_status = {
        f"space{i}": R_states[f"R{i}"] in ["D", "W"]
        for i in range(1, 5)
    }
    total_umbrellas = sum(1 for state in R_states.values() if state in ["D", "W"])

    stand_ref.update({
        "spaces": spaces_status,
        "totalUmbrellas": total_umbrellas,
    })


def control_fans():
    # 건조 중인 우산이 하나라도 있으면 팬을 켭니다.
    global fan_status

    if any(state == "W" for state in R_states.values()):
        if not fan_status:
            for fan in fans:
                fan.on()
            fan_status = True
    else:
        if fan_status:
            for fan in fans:
                fan.off()
            fan_status = False


def timer_thread_func(space_number):
    # 건조 타이머 종료 후 보관함 상태를 D로 변경합니다.
    timer_name = f"timer{space_number}"

    while timers[timer_name] > 0:
        with timer_lock:
            if active_timers[timer_name]:
                timers[timer_name] -= 1
        sleep(1)

    if R_states[f"R{space_number}"] == "W":
        R_states[f"R{space_number}"] = "D"
        active_timers[timer_name] = False
        update_firebase_status()
        control_fans()


def control_solenoid(space_number):
    # 선택된 보관함의 솔레노이드를 작동시키고 버튼 상태 변화를 감지합니다.
    if space_number not in solenoids:
        print(f"Invalid space number: {space_number}")
        return

    solenoid = solenoids[space_number]
    button = buttons[space_number]
    r_state = f"R{space_number}"
    timer_name = f"timer{space_number}"

    solenoid.on()
    print(f"space{space_number} lock opened")

    def handle_button_change():
        button.when_pressed = None
        button.when_released = None

        if button.is_pressed:
            # 우산이 들어온 상태: 반납 또는 건조 시작
            R_states[r_state] = "W"
            timers[timer_name] = 5
            active_timers[timer_name] = True

            if timer_name not in timer_threads or not timer_threads[timer_name].is_alive():
                t = threading.Thread(target=timer_thread_func, args=(space_number,), daemon=True)
                t.start()
                timer_threads[timer_name] = t

            time.sleep(1)
            solenoid.off()
            control_fans()
        else:
            # 우산이 빠진 상태: 대여 완료
            R_states[r_state] = "N"
            timers[timer_name] = 5
            active_timers[timer_name] = False
            solenoid.off()
            control_fans()

        update_firebase_status()

        # 다음 입력을 받을 수 있도록 이벤트 핸들러 재등록
        sleep(0.5)
        button.when_pressed = handle_button_change
        button.when_released = handle_button_change

    button.when_pressed = handle_button_change
    button.when_released = handle_button_change


def rental_request_listener(event):
    # Firebase rental_request/space_id 값 변경을 감지합니다.
    requested_space = event.data

    if requested_space is None:
        return

    if isinstance(requested_space, str) and requested_space.startswith("space"):
        try:
            space_number = int(requested_space.replace("space", ""))
            control_solenoid(space_number)
        except ValueError:
            print(f"Invalid request value: {requested_space}")
    else:
        print(f"Invalid request value: {requested_space}")


def process_input(value):
    if value in solenoids:
        control_solenoid(value)


def set_state(r_num, state):
    if r_num in R_states and state in ["D", "W", "N"]:
        R_states[r_num] = state
        control_fans()
        update_firebase_status()
    else:
        print("Use format: set R1 D / set R2 W / set R3 N")


def safe_exit():
    for solenoid in solenoids.values():
        solenoid.off()
    for fan in fans:
        fan.off()
    print("GPIO outputs turned off. Program exited safely.")


if __name__ == "__main__":
    try:
        update_firebase_status()
        rental_request_ref.listen(rental_request_listener)

        while True:
            x = input("input 1,2,3,4 or [set Rx D,W,N]: ").strip()

            if x.startswith("set"):
                _, r_num, state = x.split()
                set_state(r_num, state)
            elif x.isdigit():
                process_input(int(x))
            else:
                sleep(0.1)

    except KeyboardInterrupt:
        safe_exit()
