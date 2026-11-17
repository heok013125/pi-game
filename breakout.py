import time, random
import board, digitalio
from PIL import Image, ImageDraw
from adafruit_rgb_display import st7789

W = H = 240
FPS = 20

# 화면 연결
cs  = digitalio.DigitalInOut(board.CE0)
dc  = digitalio.DigitalInOut(board.D25)
rst = digitalio.DigitalInOut(board.D24)

bl = digitalio.DigitalInOut(board.D26)  # 백라이트
bl.switch_to_output()
bl.value = True

spi = board.SPI()
disp = st7789.ST7789(spi, width=W, height=H, rotation=180, y_offset=80,
                     cs=cs, dc=dc, rst=rst, baudrate=24000000)

# 버튼 준비 (누르면 value가 False)
def btn(pin):
    d = digitalio.DigitalInOut(pin)
    d.direction = digitalio.Direction.INPUT
    d.pull = digitalio.Pull.UP
    return d

LEFT, RIGHT = btn(board.D27), btn(board.D23)
RESET = btn(board.D5)  # A 버튼 (가이드는 CENTER였음)

img = Image.new("RGB", (W, H))
draw = ImageDraw.Draw(img)

# 게임 처음 상태 
life = 3                    # 목숨 3개
player = [W // 2, H - 40]   # 바 위치 [가로, 세로] → 화면 가운데 아래쪽
vx = 3                      # 공의 가로 속도 (+면 오른쪽, -면 왼쪽)
vy = 3                      # 공의 세로 속도 (+면 아래, -면 위)
ball = [W // 2, 40]         # 공 위치 [가로, 세로] → 화면 가운데 위쪽
score = 0                   # 점수
speed = 4                   # 바가 한 번에 움직이는 칸 수
state = "PLAY"              # 지금 게임 상태: "PLAY"(플레이 중) 또는 "OVER"(끝)

# 시간 재기 준비 
prev = time.monotonic()     # 지난번에 시계를 본 시각
acc = 0.0                   # 아직 처리 못 한 시간이 쌓이는 통
STEP = 1 / 60               # 게임 규칙은 1/60초마다 한 번씩 계산

# 게임 무한 반복
while True:
    # 시간이 얼마나 지났나 재기
    now = time.monotonic()  # 지금 시각
    acc += now - prev       # 지난번부터 흐른 시간을 통에 넣기
    prev = now              # 지금 시각을 "지난번"으로 기억
    if acc > 0.25:          # 너무 많이 쌓였으면 (컴퓨터가 잠깐 멈췄던 경우)
        acc = 0.0           # 통을 비워서 공이 순간이동하지 않게

    # 게임 규칙 계산 (통에 1/60초 이상 쌓여 있으면 계속)
    while acc >= STEP:

        # ===== 게임 하는 중일 때 =====
        if state == "PLAY":
            # 바 움직이기
            if not LEFT.value:          # 왼쪽 버튼 눌렸으면
                player[0] -= speed      #   바를 왼쪽으로
            if not RIGHT.value:         # 오른쪽 버튼 눌렸으면
                player[0] += speed      #   바를 오른쪽으로
            player[0] = max(12, min(W - 12, player[0]))  # 바가 화면 밖으로 못 나가게

            # 공 움직이기
            ball[0] += vx               # 가로로 vx만큼
            ball[1] += vy               # 세로로 vy만큼

            # 공이 왼쪽 벽에 닿으면 → 무조건 오른쪽으로
            if ball[0] <= 6:
                vx = abs(vx)
            # 공이 오른쪽 벽에 닿으면 → 무조건 왼쪽으로
            elif ball[0] >= W - 6:
                vx = -abs(vx)

            # 공이 천장에 닿으면 → 무조건 아래로
            if ball[1] <= 6:
                vy = abs(vy)

            # 공이 바닥에 닿으면 → 목숨 하나 잃기
            if ball[1] > H - 6:
                life -= 1               # 목숨 -1
                if life <= 0:           # 목숨이 다 떨어졌으면
                    state = "OVER"      #   게임 끝
                ball = [W // 2, 40]     # 공을 처음 자리로
                vy = abs(vy)            # 아래로 출발

            # 내려오던 공이 바에 닿으면 → 무조건 위로
            if abs(ball[1] - player[1]) < 12 and abs(ball[0] - player[0]) < 26 and vy > 0:
                vy = -abs(vy)

            # 게임 중에 A 버튼 누르면 점수 0
            if not RESET.value:
                score = 0

        # ===== 게임이 끝났을 때 =====
        elif state == "OVER":
            if not RESET.value:          # A 버튼 누르면 처음부터 다시
                life = 3
                score = 0
                player = [W // 2, H - 40]
                ball = [W // 2, 40]
                vx = 3
                vy = 3
                state = "PLAY"

        # 1/60초만큼 처리했으니 통에서 빼기 (상태 상관없이 항상)
        acc -= STEP

    # 그리기
    draw.rectangle((0, 0, W, H), fill=(10, 10, 25))
    if state == "PLAY":
        draw.rectangle((player[0] - 20, player[1] - 6,
                        player[0] + 20, player[1] + 6), fill=(0, 220, 140))
        draw.ellipse((ball[0] - 6, ball[1] - 6,
                    ball[0] + 6, ball[1] + 6), fill=(255, 200, 0))
        draw.text((8, 8), f"SCORE {score} LIFE {life}", fill=(255, 255, 255))
    elif state == "OVER":
        draw.text((93, 114), "GAME OVER", fill=(255, 255, 255))
        draw.text((70, 136), "PRESS A TO RESTART", fill=(255, 255, 255))
    disp.image(img)


    time.sleep(max(0, 1 / FPS - (time.monotonic() - now)))
    