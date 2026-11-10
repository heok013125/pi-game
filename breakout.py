import time, random
import board, digitalio
from PIL import Image, ImageDraw
from adafruit_rgb_display import st7789

W = H = 240
FPS = 10

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

# 게임 상태
player = [W // 2, H - 40]
vx = 3
vy = 3
ball = [W // 2, 40]
score = 0
speed = 4

prev = time.monotonic()
acc = 0.0
STEP = 1 / 60

while True:
    now = time.monotonic()
    acc += now - prev
    prev = now
    if acc > 0.25:
        acc = 0.0

    # 로직: 1/60초 단위로 처리
    while acc >= STEP:
        if not LEFT.value:
            player[0] -= speed
        if not RIGHT.value:
            player[0] += speed
        player[0] = max(12, min(W - 12, player[0]))

        ball[0] += vx
        ball[1] += vy

        if ball[0] <= 6 :
            vx = abs(vx)
        elif ball[0] >= W - 6 :
            vx = -abs(vx)

        if ball[1] <= 6 :
            vx = abs(vy)
        elif ball[1] >= H - 6 :
            vx = -abs(vy)


        if abs(ball[1] - player[1]) < 12 and abs(ball[0] - player[0]) < 20:  # 받음
            ball[1] = 0
            ball[0] = random.randint(20, W - 20)
            score += 1

        if not RESET.value:
            score = 0

        acc -= STEP

    # 그리기
    draw.rectangle((0, 0, W, H), fill=(10, 10, 25))
    draw.rectangle((player[0] - 20, player[1] - 6,
                    player[0] + 20, player[1] + 6), fill=(0, 220, 140))
    draw.ellipse((ball[0] - 6, ball[1] - 6,
                  ball[0] + 6, ball[1] + 6), fill=(255, 200, 0))
    draw.text((8, 8), f"SCORE {score}", fill=(255, 255, 255))
    disp.image(img)

    time.sleep(max(0, 1 / FPS - (time.monotonic() - now)))