# == 도구 가져오기 ==
# 시간 재기(time), 무작위 숫자(random)
import time, random
# 라즈베리파이 핀 사용 도구
import board, digitalio
# 그림 그리는 도구 (ImageFont: 글씨체/글씨 크기 정하는 도구)
from PIL import Image, ImageDraw, ImageFont
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
    # 안 누를 때는 True가 되게 하기0
    d.pull = digitalio.Pull.UP
    return d

# 조이스틱 왼쪽, 오른쪽 (바 이동)
LEFT, RIGHT = btn(board.D27), btn(board.D23)
# A 버튼 (시작 / 선택 / 다음 라운드 / 메뉴로 돌아가기)
RESET = btn(board.D5)

# == 도화지 준비 ==
# 240x240 크기의 빈 도화지
img = Image.new("RGB", (W, H))
# 도화지에 그림을 그리는 붓
draw = ImageDraw.Draw(img)

# == 글씨 준비 ==
# 글씨체 파일에서 원하는 크기의 글씨 만들기 (파일이 없으면 None = 기본 작은 글씨 사용)
def load_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return None

# 제목용 큰 글씨, 메뉴용 중간 글씨
FONT_BIG = load_font(34)
FONT_MID = load_font(18)

# 글씨를 화면 가로 가운데에 쓰는 함수 (y: 글씨 위쪽 높이)
def center_text(y, text, font=None, fill=(255, 255, 255)):
    # 글씨 가로 길이 재기 (실패하면 글자 하나 6칸으로 대충 계산)
    try:
        w = draw.textlength(text, font=font)
    except Exception:
        w = len(text) * 6
    # 화면 가운데에서 글씨 길이의 절반만큼 왼쪽에서 시작
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)

# == 테두리 바 설정 (4, 5라운드 전용) ==
# 바가 다니는 길은 화면 가장자리에서 12칸 안쪽의 네모 모양 길
M = 12
# 길 한 변의 길이 (216)
SIDE = W - 2 * M
# 길 한 바퀴의 길이 (864)
PERIM = 4 * SIDE
# 변마다 공이 바에서 멀어지는 방향 (위쪽 변: 아래로 +1 / 오른쪽 변: 왼쪽으로 -1 / 아래쪽 변: 위로 -1 / 왼쪽 변: 오른쪽으로 +1)
AWAY = [1, -1, -1, 1]
# 변마다 바가 화면에서 움직이는 방향 (위쪽 변: 오른쪽 +1 / 오른쪽 변: 아래 +1 / 아래쪽 변: 왼쪽 -1 / 왼쪽 변: 위 -1)
TANG = [1, 1, -1, -1]

# 길 위의 거리 s를 화면 좌표 (x, y)로 바꾸는 함수
# s=0은 왼쪽 위 모서리, 시계 방향으로 갈수록 s가 커짐
# 위쪽 변(0) → 오른쪽 변(1) → 아래쪽 변(2) → 왼쪽 변(3)
def path_point(s):
    # 한 바퀴 넘어가면 처음으로 돌아오게
    s = s % PERIM
    # 몇 번째 변인지 (0~3)
    e = int(s // SIDE)
    # 그 변의 시작점에서 얼마나 갔는지
    t = s - e * SIDE
    # 위쪽 변: 왼쪽 → 오른쪽
    if e == 0:
        return (M + t, M)
    # 오른쪽 변: 위 → 아래
    elif e == 1:
        return (W - M, M + t)
    # 아래쪽 변: 오른쪽 → 왼쪽
    elif e == 2:
        return (W - M - t, H - M)
    # 왼쪽 변: 아래 → 위
    else:
        return (M, H - M - t)

# 테두리 바가 차지하는 네모들을 돌려주는 함수 ([(변 번호, (x1, y1, x2, y2)), ...])
# s: 바 가운데의 거리, half: 바 길이의 절반
# 모서리에 걸치면 변마다 네모가 하나씩 나와서 L자 모양이 됨
def border_rects(s, half):
    # 결과를 담을 빈 상자
    rects = []
    # 바가 차지하는 길 구간 (시작, 끝)
    lo, hi = s - half, s + half
    # 구간들 (한 바퀴 이음새 0을 넘으면 두 조각으로 나눔)
    spans = []
    if lo < 0:
        spans.append((lo + PERIM, PERIM))
        spans.append((0, hi))
    elif hi > PERIM:
        spans.append((lo, PERIM))
        spans.append((0, hi - PERIM))
    else:
        spans.append((lo, hi))
    # 구간마다, 변마다 겹치는 부분을 네모로 만들기
    for a, b in spans:
        for e in range(4):
            # 이 변이 차지하는 길 구간
            ea, eb = e * SIDE, (e + 1) * SIDE
            # 바 구간과 이 변 구간이 겹치는 부분
            lo2, hi2 = max(a, ea), min(b, eb)
            # 안 겹치면 다음 변으로
            if lo2 >= hi2:
                continue
            # 겹친 부분의 양 끝을 화면 좌표로 바꾸기
            x1, y1 = path_point(lo2)
            x2, y2 = path_point(hi2)
            # 바 두께(위아래/양옆 6칸씩)를 붙여서 네모로 저장
            rects.append((e, (min(x1, x2) - 6, min(y1, y2) - 6,
                              max(x1, x2) + 6, max(y1, y2) + 6)))
    return rects

# == 벽돌 색 설정 ==
# 줄마다 다른 색 (줄이 색 개수보다 많으면 처음 색부터 다시 반복)
ROW_COLORS = [(230, 80, 80), (240, 160, 60), (240, 220, 80), (90, 200, 120)]

# == 라운드 설정표 ==
# bars  : (x, y, 방향부호, 위치)
#         방향부호 +1: 입력과 같은 방향 / -1: 반대 방향
#         위치 "bottom": 아래 바 / "top": 위 바 / "border": 테두리 바
#         테두리 바는 x 자리에 길 위의 거리 s를 넣음 (540 = 아래쪽 변 가운데, 108 = 위쪽 변 가운데)
# launch: 공이 바 위에서 나올 때(처음 시작할 때, 놓친 뒤)의 속도 (바 앞쪽으로 똑바로 나감)
# bar_half   : 바 길이의 절반 (80이면 전체 길이 160 / 테두리 라운드에서 108이면 한 변을 꽉 채움)
# bar_speed  : 바가 한 번에 움직이는 칸 수
# border     : True면 테두리 바 라운드 (벽 없이 사방이 뚫려 있음)
# brick_top  : 벽돌 첫 줄이 시작하는 높이
# brick_rows : 벽돌 줄 수
# brick_w/h  : 벽돌 하나의 가로/세로 크기
# gap        : 벽돌 사이 간격
# cols       : 한 줄에 들어가는 벽돌 칸 수 (벽돌 덩어리는 화면 가운데에 자동으로 맞춰짐)
# hole       : 비워 둘 칸 범위 (시작칸, 끝칸). (4, 10)이면 4~9번 칸을 비움. None이면 안 비움
# top_open   : True면 천장이 뚫려 있어서 위로 나간 공은 놓친 것
STAGES = [
    {   # 1라운드: 바 1개, 공 1개
        "bars":  [(W // 2, H - 40, 1, "bottom")],
        "launch": 4.2,
        "bar_half": 80, "bar_speed": 4, "border": False,
        "brick_top": 30, "brick_rows": 4,
        "brick_w": 26, "brick_h": 12, "gap": 4, "cols": 8,
        "hole": None,
        "top_open": False,
    },
    {   # 2라운드: 위·아래 바 2개(같은 방향), 공 1개, 작은 벽돌을 가운데에 많이
        "bars":  [(W // 2, H - 40, 1, "bottom"), (W // 2, 40, 1, "top")],
        "launch": 3.6,
        "bar_half": 80, "bar_speed": 4, "border": False,
        "brick_top": 91, "brick_rows": 6,
        "brick_w": 14, "brick_h": 8, "gap": 2, "cols": 8,
        "hole": None,
        "top_open": True,
    },
    {   # 3라운드: 위·아래 바 2개(서로 반대 방향), 공 1개, 벽돌은 양옆에만
        "bars":  [(W // 2, H - 40, 1, "bottom"), (W // 2, 40, -1, "top")],
        "launch": 3.6,
        "bar_half": 80, "bar_speed": 4, "border": False,
        "brick_top": 91, "brick_rows": 6,
        "brick_w": 14, "brick_h": 8, "gap": 2, "cols": 14,
        "hole": (4, 10),
        "top_open": True,
    },
    {   # 4라운드: 테두리 바 2개(아래쪽 변, 위쪽 변에서 시작, 화면에선 서로 반대로 움직임), 공 1개, 벽 없음
        "bars":  [(540, 0, 1, "border"), (108, 0, 1, "border")],
        "launch": 2.8,
        "bar_half": 108, "bar_speed": 5, "border": True,
        "brick_top": 81, "brick_rows": 8,
        "brick_w": 14, "brick_h": 8, "gap": 2, "cols": 5,
        "hole": None,
        "top_open": False,
    },
    {   # 5라운드: 한 변을 꽉 채우는 긴 바 1개가 테두리를 돎, 공 1개, 벽 없음 (선택 과제)
        "bars":  [(540, 0, 1, "border")],
        "launch": 2.8,
        "bar_half": 108, "bar_speed": 5, "border": True,
        "brick_top": 81, "brick_rows": 8,
        "brick_w": 14, "brick_h": 8, "gap": 2, "cols": 5,
        "hole": None,
        "top_open": False,
    },
]

# == 도우미 함수 ==
# 벽돌 만들기: 라운드 번호를 받아서 그 라운드 설정대로 벽돌 목록을 돌려줌
def make_bricks(n):
    # 이 라운드의 설정 가져오기
    cfg = STAGES[n - 1]
    # 벽돌 크기, 간격, 칸 수를 짧은 이름으로 꺼내기
    bw, bh, gap, cols = cfg["brick_w"], cfg["brick_h"], cfg["gap"], cfg["cols"]
    # 비워 둘 칸 범위 (없으면 None)
    hole = cfg["hole"]
    # 벽돌 한 줄의 전체 가로 길이 (벽돌 크기 x 개수 + 사이 간격 x (개수-1))
    total = cols * bw + (cols - 1) * gap
    # 한 줄이 화면 가운데에 오도록 시작 x 구하기 (양옆 여백이 같아짐)
    left = (W - total) // 2
    # 벽돌을 담을 빈 상자
    result = []
    # 줄 번호: 0, 1, 2 ...
    for row in range(cfg["brick_rows"]):
        # 칸 번호: 0, 1, ... cols-1
        for col in range(cols):
            # 비워 두는 칸이면 벽돌을 안 만들고 다음 칸으로
            if hole is not None and hole[0] <= col < hole[1]:
                continue
            # 벽돌 왼쪽 위 x: 칸이 늘수록 오른쪽으로
            x = left + col * (bw + gap)
            # 벽돌 왼쪽 위 y: 줄이 늘수록 아래로
            y = cfg["brick_top"] + row * (bh + gap)
            # [x, y, 줄번호] 저장 (줄번호는 색 고를 때 사용)
            result.append([x, y, row])
    return result

# 바 만들기: 설정표에서 복사본을 만들어서 돌려줌 (원본이 안 바뀌게)
def make_bars(n):
    return [list(b) for b in STAGES[n - 1]["bars"]]

# 공이 나올 때 옆으로 기우는 정도 (속력의 몇 %를 옆으로 보낼지)
# 0이면 똑바로, 0.2면 약 11도, 0.5면 약 30도
LAUNCH_SIDE = 0.2

# 공 만들기: 첫 번째 바 바로 앞에서, 바 앞쪽으로 살짝 기울어져 날아가는 공 하나를 돌려줌
# (라운드 처음 시작할 때, 공을 놓친 뒤 둘 다 이 함수를 씀)
def respawn_ball(n, bars):
    # 이 라운드의 설정과 공이 나올 때의 속도
    cfg = STAGES[n - 1]
    sp = cfg["launch"]
    # 옆으로 가는 속도: 왼쪽/오른쪽 중 랜덤으로, 속력의 LAUNCH_SIDE만큼만
    side = random.choice([-1, 1]) * sp * LAUNCH_SIDE
    # 앞쪽으로 가는 속도: 전체 속력이 sp로 그대로 유지되게 나머지로 계산
    fwd = (sp * sp - side * side) ** 0.5
    # 첫 번째 바 (보통 라운드에선 아래 바, 테두리 라운드에선 첫 번째 테두리 바)
    bar = bars[0]
    # 테두리 라운드: 바가 있는 변의 안쪽 방향으로 나감
    if cfg["border"]:
        # 바 가운데의 거리와 몇 번째 변인지
        s = bar[0] % PERIM
        e = int(s // SIDE)
        # 그 변 위에서 어디쯤인지 (모서리에서 20칸 이상 떨어지게 잡아서 L자 날개에 안 끼게)
        t = max(20, min(SIDE - 20, s - e * SIDE))
        # 그 위치의 화면 좌표
        px, py = path_point(e * SIDE + t)
        # 위쪽/아래쪽 변: 바에서 14칸 띄워서, 세로로 나가고 가로로 살짝 기움
        if e == 0 or e == 2:
            return [px, py + AWAY[e] * 14, side, AWAY[e] * fwd]
        # 왼쪽/오른쪽 변: 바에서 14칸 띄워서, 가로로 나가고 세로로 살짝 기움
        else:
            return [px + AWAY[e] * 14, py, AWAY[e] * fwd, side]
    # 보통 라운드: 아래 바 바로 위(14칸)에서 위로 나가고 옆으로 살짝 기움
    return [bar[0], bar[1] - 14, side, -fwd]

# 공을 바에서 튕겨 내기 (바가 움직이고 있으면 그 방향으로 날아가게)
# axis: 0이면 위/아래 바(공의 세로 속도를 바꿈), 1이면 왼쪽/오른쪽 바(가로 속도를 바꿈)
# away: 바에서 멀어지는 방향 부호 (+1 또는 -1)
# lat : 바가 화면에서 움직이는 방향 부호 (-1, 0, +1) / 0이면 안 움직임
def bounce_off_bar(ball, axis, away, lat):
    # 공의 속력 (가로 속도와 세로 속도를 합친 길이, 튕겨도 이건 그대로)
    sp = (ball[2] ** 2 + ball[3] ** 2) ** 0.5
    # n: 바에서 멀어지는 쪽 속도 번호 / t: 바를 따라가는 쪽 속도 번호
    if axis == 0:
        n, t = 3, 2
    else:
        n, t = 2, 3
    # 바가 움직이고 있으면, 바를 따라가는 속도를 바 이동 방향으로 (속력의 80%)
    if lat != 0:
        ball[t] = lat * 0.8 * sp
    # 바에서 멀어지는 속도는 남은 속력으로 (속력이 변하지 않게)
    ball[n] = away * max(0.0, sp * sp - ball[t] * ball[t]) ** 0.5

# == 게임 처음 상태 ==
# 게임을 시작할 때 목숨 개수
START_LIFE = 5
# 점수
score = 0
# 지금 라운드 번호
stage = 1
# 선택 화면에서 가리키고 있는 라운드 번호
cursor = 1
# 지금 게임 상태:
# "TITLE"(제목 화면) / "SELECT"(라운드 고르기) / "PLAY"(하는 중)
# "CLEAR"(라운드 클리어) / "ALLCLEAR"(전부 클리어) / "OVER"(끝)
state = "TITLE"
# 바 목록
bars = make_bars(stage)
# 공 목록 (공 하나는 [x, y, vx, vy]) - 바 앞에서 시작
balls = [respawn_ball(stage, bars)]
# 벽돌 목록
bricks = make_bricks(stage)

# == 버튼 "눌린 순간" 확인 준비 ==
# 지난번 확인 때 버튼이 눌려 있었는지 (처음엔 다 안 눌린 걸로)
a_prev = l_prev = r_prev = False

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
        # 지금 라운드의 벽돌 가로/세로 크기
        bw, bh = cfg["brick_w"], cfg["brick_h"]
        # 지금 라운드의 바 길이 절반
        bar_half = cfg["bar_half"]

        # --- 버튼이 "안 눌려 있다가 이번에 눌린 순간"인지 확인 ---
        # 지금 눌려 있는지 (누르면 value가 False라서 not을 붙임)
        a_now = not RESET.value
        l_now = not LEFT.value
        r_now = not RIGHT.value
        # 지금은 눌렸고 + 지난번엔 안 눌렸으면 "방금 눌렀다" (한 번만 True)
        a_pressed = a_now and not a_prev
        l_pressed = l_now and not l_prev
        r_pressed = r_now and not r_prev
        # 지금 상태를 다음 확인 때 쓰려고 저장
        a_prev, l_prev, r_prev = a_now, l_now, r_now

        # ===== 제목 화면: A 누르면 라운드 선택으로 =====
        if state == "TITLE":
            if a_pressed:
                state = "SELECT"

        # ===== 라운드 선택: 좌우로 고르고 A로 시작 =====
        elif state == "SELECT":
            # 왼쪽으로 한 칸 (1번보다 더 왼쪽으론 못 감)
            if l_pressed:
                cursor = max(1, cursor - 1)
            # 오른쪽으로 한 칸 (마지막 라운드보다 더 오른쪽으론 못 감)
            if r_pressed:
                cursor = min(len(STAGES), cursor + 1)
            # A 누르면 고른 라운드를 처음 상태로 시작
            if a_pressed:
                stage = cursor
                life = START_LIFE
                score = 0
                bars = make_bars(stage)
                # 공은 바를 먼저 만든 다음에 바 앞에서 생성
                balls = [respawn_ball(stage, bars)]
                bricks = make_bricks(stage)
                state = "PLAY"

        # ===== 게임 하는 중 =====
        elif state == "PLAY":
            # 바 움직이기: 입력을 -1(왼쪽), 0(없음), +1(오른쪽)로 바꾸기
            move = 0
            if l_now:
                move -= 1
            if r_now:
                move += 1
            # 바마다 "이번에 화면에서 어느 쪽으로 움직였나"를 담을 목록 (-1, 0, +1)
            bar_lat = []
            for bar in bars:
                # 테두리 라운드: 오른쪽(+1)이면 반시계 = 거리 s가 줄고, 왼쪽(-1)이면 시계 = s가 늚
                if cfg["border"]:
                    # 한 바퀴를 넘어가면 처음으로 돌아오게 % PERIM (bar[2]는 방향부호)
                    bar[0] = (bar[0] - move * cfg["bar_speed"] * bar[2]) % PERIM
                    # s가 늘면 +1, 줄면 -1, 안 움직이면 0
                    bar_lat.append(-move * bar[2])
                # 보통 라운드: 바마다 방향부호(bar[2])를 곱해서 좌우로 이동
                else:
                    # 움직이기 전 위치 기억
                    old_x = bar[0]
                    bar[0] += move * cfg["bar_speed"] * bar[2]
                    # 바가 화면 밖으로 못 나가게 (바 길이만큼 안쪽까지만)
                    bar[0] = max(bar_half, min(W - bar_half, bar[0]))
                    # 실제로 움직인 방향 (벽 끝에 막혀서 못 움직였으면 0)
                    diff = bar[0] - old_x
                    bar_lat.append((diff > 0) - (diff < 0))

            # 이번 스텝에 놓친 공들을 모아 둘 상자
            lost = []
            # 공 하나씩 처리 (ball = [x, y, vx, vy])
            for ball in balls:
                # 공 움직이기
                ball[0] += ball[2]
                ball[1] += ball[3]

                # ----- 테두리 라운드: 벽이 없고, 바에만 튕김 -----
                if cfg["border"]:
                    # 화면 밖으로 나가면 놓친 것
                    if ball[0] < 0 or ball[0] > W or ball[1] < 0 or ball[1] > H:
                        lost.append(ball)
                        continue
                    # 바마다 (i: 몇 번째 바인지)
                    for i, bar in enumerate(bars):
                        # 바가 차지하는 네모들과 겹치는지 검사 (모서리면 네모가 2개)
                        for edge, r in border_rects(bar[0], bar_half):
                            if (ball[0] + 6 > r[0] and ball[0] - 6 < r[2] and
                                ball[1] + 6 > r[1] and ball[1] - 6 < r[3]):
                                # 위/아래 변 바는 세로(0), 왼쪽/오른쪽 변 바는 가로(1)로 튕김
                                axis = 0 if (edge == 0 or edge == 2) else 1
                                # 바에서 멀어지는 방향
                                away = AWAY[edge]
                                # 공이 바 쪽으로 오는 중인지 확인할 속도 번호 (세로면 3, 가로면 2)
                                n = 3 if axis == 0 else 2
                                # 바 쪽으로 오던 공만 튕기기 (속도 부호가 away와 반대면 오는 중)
                                if ball[n] * away < 0:
                                    # 바가 이 변에서 화면상 움직인 방향 = (시계/반시계) x (변의 시계 방향)
                                    bounce_off_bar(ball, axis, away, bar_lat[i] * TANG[edge])

                # ----- 보통 라운드: 벽에 튕기고, 위/아래 바에 튕김 -----
                else:
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

                    # 바에 맞았는지 검사 (i: 몇 번째 바인지)
                    for i, bar in enumerate(bars):
                        # 세로 거리 < 12(바 두께 + 공 반지름), 가로 거리 < 바 길이 + 공 반지름
                        if abs(ball[1] - bar[1]) < 12 and abs(ball[0] - bar[0]) < bar_half + 6:
                            # 아래 바는 공을 위로(-1), 위 바는 공을 아래로(+1) 보냄
                            away = -1 if bar[3] == "bottom" else 1
                            # 바 쪽으로 오던 공만 튕기기 (속도 부호가 away와 반대면 오는 중)
                            if ball[3] * away < 0:
                                # 바가 움직이고 있었으면 그 방향으로 날아가게 튕김
                                bounce_off_bar(ball, 0, away, bar_lat[i])

                # ----- 벽돌에 맞았는지 검사 (모든 라운드 공통) -----
                for b in bricks:
                    # 공을 감싼 네모와 벽돌 네모가 겹치는지 확인 (공 반지름 6)
                    if (ball[0] + 6 > b[0] and ball[0] - 6 < b[0] + bw and
                        ball[1] + 6 > b[1] and ball[1] - 6 < b[1] + bh):

                        # 벽돌 가운데 좌표
                        cx = b[0] + bw / 2
                        cy = b[1] + bh / 2
                        # 공이 벽돌 가운데에서 가로/세로로 얼마나 떨어졌는지 (벽돌 크기로 나눠서 공평하게 비교)
                        dx = (ball[0] - cx) / (bw / 2 + 6)
                        dy = (ball[1] - cy) / (bh / 2 + 6)

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
                # 아니면 지금 바 앞에서 공 하나를 새로 만들기 (벽돌은 그대로)
                else:
                    balls = [respawn_ball(stage, bars)]

        # ===== 라운드 클리어: A 누르면 다음 라운드 =====
        elif state == "CLEAR":
            if a_pressed:
                stage += 1
                bars = make_bars(stage)
                # 공은 바를 먼저 만든 다음에 바 앞에서 생성
                balls = [respawn_ball(stage, bars)]
                bricks = make_bricks(stage)
                state = "PLAY"

        # ===== 게임 오버 / 전부 클리어: A 누르면 라운드 선택으로 =====
        elif state == "OVER" or state == "ALLCLEAR":
            if a_pressed:
                # 선택 화면에서 방금 하던 라운드를 가리키게 해 두기
                cursor = stage
                state = "SELECT"

        # 1/60초만큼 처리했으니 통에서 빼기 (상태 상관없이 항상)
        acc -= STEP

    # --- 화면 그리기 ---
    # 지금 라운드의 설정 (벽돌/바 크기를 그릴 때 사용)
    cfg = STAGES[stage - 1]
    bw, bh = cfg["brick_w"], cfg["brick_h"]
    bar_half = cfg["bar_half"]

    # 도화지를 남색으로 칠해서 지우기 (항상 가장 먼저)
    draw.rectangle((0, 0, W, H), fill=(10, 10, 25))

    # 제목 화면
    if state == "TITLE":
        # 게임 제목 (두 줄)
        center_text(60, "BRICK", FONT_BIG, fill=(255, 200, 0))
        center_text(100, "BREAKER", FONT_BIG, fill=(255, 200, 0))
        # 시작 안내
        center_text(170, "PRESS A TO START", FONT_MID)

    # 라운드 선택 화면
    elif state == "SELECT":
        # 위쪽 제목
        center_text(40, "SELECT STAGE", FONT_MID)
        # 라운드 개수
        n = len(STAGES)
        # 네모 한 칸의 크기, 칸 사이 간격 (5개가 화면에 들어오도록 36, 8)
        box, sp = 36, 8
        # 네모들 전체 가로 길이와, 가운데에 오도록 시작 x
        total = n * box + (n - 1) * sp
        left = (W - total) // 2
        # 라운드 번호 네모를 하나씩 그리기
        for i in range(n):
            # 이 네모의 왼쪽 위 좌표
            x = left + i * (box + sp)
            y = 95
            # 지금 가리키고 있는 라운드면 노란색으로 꽉 채우기
            if i + 1 == cursor:
                draw.rectangle((x, y, x + box, y + box), fill=(255, 200, 0))
                num_color = (10, 10, 25)
            # 아니면 회색 테두리만
            else:
                draw.rectangle((x, y, x + box, y + box), outline=(120, 120, 140), width=2)
                num_color = (200, 200, 200)
            # 네모 가운데에 번호 쓰기 (가운데 맞추기가 안 되는 글씨면 대충 위치로)
            try:
                draw.text((x + box // 2, y + box // 2), str(i + 1),
                          font=FONT_MID, fill=num_color, anchor="mm")
            except Exception:
                draw.text((x + box // 2 - 3, y + box // 2 - 5), str(i + 1), fill=num_color)
        # 조작 안내
        center_text(170, "< > MOVE    A: START")

    # 게임 하는 중 화면
    elif state == "PLAY":
        # 벽돌 그리기 (줄 번호를 색 개수로 나눈 나머지로 색 고르기)
        for b in bricks:
            draw.rectangle((b[0], b[1], b[0] + bw, b[1] + bh),
                           fill=ROW_COLORS[b[2] % len(ROW_COLORS)])
        # 바 그리기
        for bar in bars:
            # 테두리 바: 변마다 네모를 그려서 모서리에서 L자가 되게
            if cfg["border"]:
                for edge, r in border_rects(bar[0], bar_half):
                    draw.rectangle(r, fill=(0, 220, 140))
            # 보통 바: 가로는 바 길이, 세로는 위아래 6칸씩
            else:
                draw.rectangle((bar[0] - bar_half, bar[1] - 6,
                                bar[0] + bar_half, bar[1] + 6), fill=(0, 220, 140))
        # 공 그리기 (반지름 6칸 동그라미)
        for ball in balls:
            draw.ellipse((ball[0] - 6, ball[1] - 6, ball[0] + 6, ball[1] + 6),
                         fill=(255, 200, 0))
        # 왼쪽 위에 라운드, 점수, 목숨 쓰기
        draw.text((8, 8), f"STAGE {stage}  SCORE {score}  LIFE {life}",
                  fill=(255, 255, 255))

    # 라운드 클리어 화면
    elif state == "CLEAR":
        center_text(105, "STAGE CLEAR!")
        center_text(125, f"SCORE {score}")
        center_text(145, "PRESS A FOR NEXT")

    # 전부 클리어 화면
    elif state == "ALLCLEAR":
        center_text(105, "ALL CLEAR!")
        center_text(125, f"SCORE {score}")
        center_text(145, "PRESS A FOR MENU")

    # 게임 오버 화면
    elif state == "OVER":
        center_text(114, "GAME OVER")
        center_text(136, "PRESS A FOR MENU")

    # 다 그린 도화지를 화면으로 보내기 (이게 없으면 화면에 안 나옴)
    disp.image(img)

    # 1초에 FPS번만 그리도록 남은 시간만큼 쉬기
    time.sleep(max(0, 1 / FPS - (time.monotonic() - now)))