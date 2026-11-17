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
RESET = btn(board.D5)  # A 버튼

img = Image.new("RGB", (W, H))
draw = ImageDraw.Draw(img)

# 벽돌 설정
BRICK_W, BRICK_H = 26, 12
GAP = 4
COLS, ROWS = 8, 4
TOP = 30          # 첫 줄 시작 높이
LEFT_MARGIN = 2   # 왼쪽 여백
ROW_COLORS = [(230, 80, 80), (240, 160, 60), (240, 220, 80), (90, 200, 120)]

BALL_START = [W // 2, 120]   # 공 시작 위치 (벽돌보다 아래)

# 벽돌 만드는 함수: 부를 때마다 새 벽돌 상자를 만들어 줌
def make_bricks():
    result = []
    for row in range(ROWS):
        for col in range(COLS):
            x = LEFT_MARGIN + col * (BRICK_W + GAP)   # 왼쪽 위 x
            y = TOP + row * (BRICK_H + GAP)           # 왼쪽 위 y
            result.append([x, y, row])                # [x, y, 줄번호]
    return result

# 게임 처음 상태
life = 3                    # 목숨 3개
player = [W // 2, H - 40]   # 바 위치 [가로, 세로]
vx = 3                      # 공의 가로 속도 (+면 오른쪽, -면 왼쪽)
vy = 3                     # 공의 세로 속도 (+면 아래, -면 위) 
ball = list(BALL_START)     # 공 위치 (복사본을 만들어서 원본이 안 바뀌게)
score = 0                   # 점수
speed = 4                   # 바가 한 번에 움직이는 칸 수
state = "PLAY"              # "PLAY"(플레이 중) 또는 "OVER"(끝)
bricks = make_bricks()      # 벽돌 만들기

# 시간 재기 준비
prev = time.monotonic()
acc = 0.0
STEP = 1 / 60

# 게임 무한 반복
while True:
    # 시간이 얼마나 지났나 재기
    now = time.monotonic()
    acc += now - prev
    prev = now
    if acc > 0.25:
        acc = 0.0

    # 게임 규칙 계산
    while acc >= STEP:

        # 게임 하는 중일 때
        if state == "PLAY":
            # 바 움직이기
            if not LEFT.value:
                player[0] -= speed
            if not RIGHT.value:
                player[0] += speed
            player[0] = max(12, min(W - 12, player[0]))

            # 공 움직이기
            ball[0] += vx
            ball[1] += vy

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
                life -= 1
                if life <= 0:
                    state = "OVER"
                ball = list(BALL_START)   # 공을 시작 위치로
                vy = -abs(vy)             # 위로 출발

            # 내려오던 공이 바에 닿으면 → 무조건 위로
            if abs(ball[1] - player[1]) < 12 and abs(ball[0] - player[0]) < 26 and vy > 0:
                vy = -abs(vy)

            # 게임 중에 A 버튼 누르면 점수 0
            if not RESET.value:
                score = 0

            # 공-벽돌 충돌
            for b in bricks:
                # 네모끼리 겹쳤는지 확인 (공 반지름 6)
                if (ball[0] + 6 > b[0] and ball[0] - 6 < b[0] + BRICK_W and
                    ball[1] + 6 > b[1] and ball[1] - 6 < b[1] + BRICK_H):

                    # 벽돌 가운데 좌표
                    cx = b[0] + BRICK_W / 2
                    cy = b[1] + BRICK_H / 2

                    # 공이 벽돌 가운데에서 가로/세로로 얼마나 떨어졌나
                    dx = (ball[0] - cx) / (BRICK_W / 2 + 6)
                    dy = (ball[1] - cy) / (BRICK_H / 2 + 6)

                    if abs(dx) > abs(dy):             # 옆면에 맞은 경우
                        if ball[0] > cx:
                            vx = abs(vx)
                        else:
                            vx = -abs(vx)
                    else:                             # 위·아래 면에 맞은 경우
                        if ball[1] > cy:
                            vy = abs(vy)
                        else:
                            vy = -abs(vy)

                    bricks.remove(b)                  # 맞은 벽돌 지우기
                    break                             # 한 번에 벽돌 하나만 처리

        # 게임이 끝났을 때
        elif state == "OVER":
            if not RESET.value:          # A 버튼 누르면 처음부터 다시
                life = 3
                score = 0
                player = [W // 2, H - 40]
                ball = list(BALL_START)
                vx = 3
                vy = -3
                bricks = make_bricks()   # 벽돌도 새로
                state = "PLAY"

        # 1/60초만큼 처리했으니 통에서 빼기 (상태 상관없이 항상)
        acc -= STEP

    # 그리기
    draw.rectangle((0, 0, W, H), fill=(10, 10, 25))   # 배경 먼저 지우기
    if state == "PLAY":
        # 벽돌 그리기 (배경 위에 그려야 보임)
        for b in bricks:
            draw.rectangle((b[0], b[1],
                            b[0] + BRICK_W, b[1] + BRICK_H),
                           fill=ROW_COLORS[b[2]])
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