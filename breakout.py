# == 도구 가져오기 ==
# 시간 재기(time), 무작위 숫자(random)
import time, random
# 라즈베리파이 핀 사용 도구
import board, digitalio
# 그림 그리는 도구
from PIL import Image, ImageDraw
# 화면에 그림을 보내는 도구
from adafruit_rgb_display import st7789

# == 화면 설정 ==
# 화면 크기 (가로 240칸, 세로 240칸)
W = H = 240
# 화면을 1초에 몇 번 새로 그릴지
FPS = 20

# == 화면 연결 ==
# 화면에게 "너한테 말하는 거야"라고 알려주는 선
cs  = digitalio.DigitalInOut(board.CE0)
# 지금 보내는 게 명령인지 그림인지 알려주는 선
dc  = digitalio.DigitalInOut(board.D25)
# 화면을 처음 상태로 리셋하는 선
rst = digitalio.DigitalInOut(board.D24)

# 백라이트(화면 뒤 조명) 선
bl = digitalio.DigitalInOut(board.D26)
# 이 선은 내보내는 용도로 사용
bl.switch_to_output()
# 조명 켜기
bl.value = True

# 화면이랑 대화하는 통로(SPI) 열기
spi = board.SPI()
# 화면 만들기 (rotation=180: 거꾸로 달려 있어서 돌리기, y_offset=80: 돌리면 밀리는 만큼 당기기)
disp = st7789.ST7789(spi, width=W, height=H, rotation=180, y_offset=80,
                     cs=cs, dc=dc, rst=rst, baudrate=24000000)

# == 버튼 준비 ==
# 버튼 핀 설정 함수 (누르면 value가 False가 됨)
def btn(pin):
    d = digitalio.DigitalInOut(pin)
    # 읽는 용도
    d.direction = digitalio.Direction.INPUT
    # 안 누를 때는 True가 되게 하기
    d.pull = digitalio.Pull.UP
    return d

# 조이스틱 왼쪽, 오른쪽
LEFT, RIGHT = btn(board.D27), btn(board.D23)
# A 버튼 (다음 라운드 / 다시 시작에 사용)
RESET = btn(board.D5)

# == 도화지 준비 ==
# 240x240 크기의 빈 도화지
img = Image.new("RGB", (W, H))
# 도화지에 그림을 그리는 붓
draw = ImageDraw.Draw(img)

# == 바 설정 ==
# 바 길이의 절반 (20이면 전체 길이 40, 숫자를 키우면 바가 길어짐)
BAR_HALF = 80

# == 벽돌 설정 ==
# 벽돌 가로/세로 길이
BRICK_W, BRICK_H = 26, 12
# 벽돌 간 사이 간격
GAP = 4
# 한 줄에 들어가는 벽돌 개수
COLS = 8
# 왼쪽 여백 (양옆이 같게 남도록 계산한 값)
LEFT_MARGIN = 2
# 줄마다 다른 색 (위에서부터 1줄, 2줄, 3줄, 4줄)
ROW_COLORS = [(230, 80, 80), (240, 160, 60), (240, 220, 80), (90, 200, 120)]

# == 라운드 설정표 ==
# bars  : (x, y, 방향부호, 위치)
#         방향부호 +1: 입력과 같은 방향 / -1: 반대 방향
#         위치 "bottom": 아래 바 / "top": 위 바
# balls : (x, y, vx, vy)   vy가 음수면 위로 출발
# brick_top : 벽돌 첫 줄이 시작하는 높이
# brick_rows: 벽돌 줄 수
# top_open  : True면 천장이 뚫려 있어서 위로 나간 공은 놓친 것
STAGES = [
    {   # 1라운드: 바 1개, 공 1개
        "bars":  [(W // 2, H - 40, 1, "bottom")],
        "balls": [(W // 2, 120, 3, -3)],
        "brick_top": 30, "brick_rows": 4,
        "top_open": False,
    },
    {   # 2라운드: 위·아래 바 2개(같은 방향), 공 2개, 벽돌은 가운데
        "bars":  [(W // 2, H - 40, 1, "bottom"), (W // 2, 40, 1, "top")],
        "balls": [(W // 2 + 40, 75, -3, 1)],
        "brick_top": 98, "brick_rows": 3,
        "top_open": True,
    },
]

# == 도우미 함수 ==
# 벽돌 만들기: 시작 높이와 줄 수를 받아서 벽돌 목록을 돌려줌
def make_bricks(top, rows):
    # 벽돌을 담을 빈 상자
    result = []
    # 줄 번호: 0, 1, 2 ...
    for row in range(rows):
        # 칸 번호: 0, 1, ... COLS-1
        for col in range(COLS):
            # 벽돌 왼쪽 위 x: 칸이 늘수록 오른쪽으로
            x = LEFT_MARGIN + col * (BRICK_W + GAP)
            # 벽돌 왼쪽 위 y: 줄이 늘수록 아래로
            y = top + row * (BRICK_H + GAP)
            # [x, y, 줄번호] 저장 (줄번호는 색 고를 때 사용)
            result.append([x, y, row])
    return result

# 바 만들기: 설정표에서 복사본을 만들어서 돌려줌 (원본이 안 바뀌게)
def make_bars(n):
    return [list(b) for b in STAGES[n - 1]["bars"]]

# 공 만들기: 설정표에서 복사본을 만들어서 돌려줌
def make_balls(n):
    return [list(b) for b in STAGES[n - 1]["balls"]]

# == 게임 처음 상태 ==
# 목숨 3개
life = 3
# 점수
score = 0
# 바가 한 번에 움직이는 칸 수
speed = 4
# 지금 라운드 번호
stage = 1
# 지금 게임 상태: "PLAY"(하는 중) / "CLEAR"(라운드 클리어) / "ALLCLEAR"(전부 클리어) / "OVER"(끝)
state = "PLAY"
# 바 목록
bars = make_bars(stage)
# 공 목록 (공 하나는 [x, y, vx, vy])
balls = make_balls(stage)
# 벽돌 목록
bricks = make_bricks(STAGES[stage - 1]["brick_top"], STAGES[stage - 1]["brick_rows"])

# == 시간 재기 준비 ==
# 지난번에 시계를 본 시각
prev = time.monotonic()
# 아직 처리 못 한 시간이 쌓이는 통
acc = 0.0
# 게임 규칙은 1/60초마다 한 번씩 계산
STEP = 1 / 60

# == 게임 무한 반복 ==
while True:
    # --- 시간이 얼마나 지났나 재기 ---
    # 지금 시각
    now = time.monotonic()
    # 지난번부터 흐른 시간을 통에 넣기
    acc += now - prev
    # 지금 시각을 지난번으로 기억
    prev = now
    # 너무 많이 쌓였으면 (잠깐 멈췄던 경우) 통을 비워서 공이 순간이동하지 않게
    if acc > 0.25:
        acc = 0.0

    # --- 게임 규칙 계산 (통에 1/60초 이상 쌓여 있으면 계속) ---
    while acc >= STEP:
        # 지금 라운드의 설정
        cfg = STAGES[stage - 1]

        # ===== 게임 하는 중 =====
        if state == "PLAY":
            # 바 움직이기: 입력을 -1(왼쪽), 0(없음), +1(오른쪽)로 바꾸기
            move = 0
            if not LEFT.value:
                move -= 1
            if not RIGHT.value:
                move += 1
            for bar in bars:
                # 바마다 방향부호(bar[2])를 곱해서 이동
                bar[0] += move * speed * bar[2]
                # 바가 화면 밖으로 못 나가게 (바 길이 BAR_HALF만큼 안쪽까지만)
                bar[0] = max(BAR_HALF, min(W - BAR_HALF, bar[0]))

            # 이번 스텝에 놓친 공들을 모아 둘 상자
            lost = []
            # 공 하나씩 처리 (ball = [x, y, vx, vy])
            for ball in balls:
                # 공 움직이기
                ball[0] += ball[2]
                ball[1] += ball[3]

                # 왼쪽 벽에 닿으면 무조건 오른쪽으로
                if ball[0] <= 6:
                    ball[2] = abs(ball[2])
                # 오른쪽 벽에 닿으면 무조건 왼쪽으로
                elif ball[0] >= W - 6:
                    ball[2] = -abs(ball[2])

                # 천장이 뚫려 있는 라운드: 위로 나가면 놓친 것
                if cfg["top_open"]:
                    if ball[1] < 6:
                        lost.append(ball)
                        continue
                # 천장이 막힌 라운드: 닿으면 무조건 아래로
                else:
                    if ball[1] <= 6:
                        ball[3] = abs(ball[3])

                # 바닥으로 나가면 놓친 것
                if ball[1] > H - 6:
                    lost.append(ball)
                    continue

                # 바에 맞았는지 검사
                for bar in bars:
                    # 세로 거리 < 12(바 두께 + 공 반지름), 가로 거리 < 바 길이 + 공 반지름
                    if abs(ball[1] - bar[1]) < 12 and abs(ball[0] - bar[0]) < BAR_HALF + 6:
                        # 아래 바: 내려오던 공만 위로 튕기기
                        if bar[3] == "bottom" and ball[3] > 0:
                            ball[3] = -abs(ball[3])
                        # 위 바: 올라가던 공만 아래로 튕기기
                        elif bar[3] == "top" and ball[3] < 0:
                            ball[3] = abs(ball[3])

                # 벽돌에 맞았는지 검사
                for b in bricks:
                    # 공을 감싼 네모와 벽돌 네모가 겹치는지 확인 (공 반지름 6)
                    if (ball[0] + 6 > b[0] and ball[0] - 6 < b[0] + BRICK_W and
                        ball[1] + 6 > b[1] and ball[1] - 6 < b[1] + BRICK_H):

                        # 벽돌 가운데 좌표
                        cx = b[0] + BRICK_W / 2
                        cy = b[1] + BRICK_H / 2
                        # 공이 벽돌 가운데에서 가로/세로로 얼마나 떨어졌는지 (벽돌 크기로 나눠서 공평하게 비교)
                        dx = (ball[0] - cx) / (BRICK_W / 2 + 6)
                        dy = (ball[1] - cy) / (BRICK_H / 2 + 6)

                        # 옆면에 맞은 경우: 가로 방향을 바꿈
                        if abs(dx) > abs(dy):
                            if ball[0] > cx:
                                ball[2] = abs(ball[2])
                            else:
                                ball[2] = -abs(ball[2])
                        # 위·아래 면에 맞은 경우: 세로 방향을 바꿈
                        else:
                            if ball[1] > cy:
                                ball[3] = abs(ball[3])
                            else:
                                ball[3] = -abs(ball[3])

                        # 맞은 벽돌 지우기
                        bricks.remove(b)
                        # 점수 +1
                        score += 1
                        # 한 번에 벽돌 하나만 처리
                        break

            # 놓친 공은 공 목록에서 빼기
            for ball in lost:
                balls.remove(ball)

            # 벽돌을 다 깼으면 클리어
            if not bricks:
                # 마지막 라운드면 전부 클리어
                if stage == len(STAGES):
                    state = "ALLCLEAR"
                # 아니면 다음 라운드로 갈 수 있는 클리어
                else:
                    state = "CLEAR"
            # 벽돌이 남았는데 공이 하나도 없으면 목숨 -1
            elif not balls:
                life -= 1
                # 목숨이 다 떨어지면 게임 끝
                if life <= 0:
                    state = "OVER"
                # 아니면 공만 다시 시작 (벽돌은 그대로)
                else:
                    balls = make_balls(stage)

        # ===== 라운드 클리어: A 누르면 다음 라운드 =====
        elif state == "CLEAR":
            if not RESET.value:
                stage += 1
                bars = make_bars(stage)
                balls = make_balls(stage)
                bricks = make_bricks(STAGES[stage - 1]["brick_top"],
                                     STAGES[stage - 1]["brick_rows"])
                state = "PLAY"

        # ===== 게임 오버 / 전부 클리어: A 누르면 처음부터 =====
        elif state == "OVER" or state == "ALLCLEAR":
            if not RESET.value:
                life = 3
                score = 0
                stage = 1
                bars = make_bars(stage)
                balls = make_balls(stage)
                bricks = make_bricks(STAGES[0]["brick_top"], STAGES[0]["brick_rows"])
                state = "PLAY"

        # 1/60초만큼 처리했으니 통에서 빼기 (상태 상관없이 항상)
        acc -= STEP

    # --- 화면 그리기 ---
    # 도화지를 남색으로 칠해서 지우기 (항상 가장 먼저)
    draw.rectangle((0, 0, W, H), fill=(10, 10, 25))

    # 게임 하는 중 화면
    if state == "PLAY":
        # 벽돌 그리기
        for b in bricks:
            draw.rectangle((b[0], b[1], b[0] + BRICK_W, b[1] + BRICK_H),
                           fill=ROW_COLORS[b[2]])
        # 바 그리기 (가로는 바 길이 BAR_HALF, 세로는 위아래 6칸씩)
        for bar in bars:
            draw.rectangle((bar[0] - BAR_HALF, bar[1] - 6,
                            bar[0] + BAR_HALF, bar[1] + 6), fill=(0, 220, 140))
        # 공 그리기 (반지름 6칸 동그라미)
        for ball in balls:
            draw.ellipse((ball[0] - 6, ball[1] - 6, ball[0] + 6, ball[1] + 6),
                         fill=(255, 200, 0))
        # 왼쪽 위에 라운드, 점수, 목숨 쓰기
        draw.text((8, 8), f"STAGE {stage}  SCORE {score}  LIFE {life}",
                  fill=(255, 255, 255))

    # 라운드 클리어 화면
    elif state == "CLEAR":
        draw.text((84, 105), "STAGE CLEAR!", fill=(255, 255, 255))
        draw.text((70, 125), f"SCORE {score}", fill=(255, 255, 255))
        draw.text((62, 145), "PRESS A FOR NEXT", fill=(255, 255, 255))

    # 전부 클리어 화면
    elif state == "ALLCLEAR":
        draw.text((88, 105), "ALL CLEAR!", fill=(255, 255, 255))
        draw.text((90, 125), f"SCORE {score}", fill=(255, 255, 255))
        draw.text((58, 145), "PRESS A TO RESTART", fill=(255, 255, 255))

    # 게임 오버 화면
    elif state == "OVER":
        draw.text((93, 114), "GAME OVER", fill=(255, 255, 255))
        draw.text((70, 136), "PRESS A TO RESTART", fill=(255, 255, 255))

    # 다 그린 도화지를 화면으로 보내기 (이게 없으면 화면에 안 나옴)
    disp.image(img)

    # 1초에 FPS번만 그리도록 남은 시간만큼 쉬기
    time.sleep(max(0, 1 / FPS - (time.monotonic() - now)))