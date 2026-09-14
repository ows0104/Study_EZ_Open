"""도는 동안만 기계를 깨워 둔다. 죽으면 저절로 풀린다 — 설정을 안 바꾼다.

노트북이 자면 `claude -p` 세션은 아무것도 못 하는데 pdf2anki 의 단계 시한은
**벽시계로** 흐른다. 깨어났을 때는 이미 「3600초 안에 끝나지 않았다」다.
2026-09-01 에 그렇게 두 편을 잃었다. 예약 작업은 기계를 못 깨운다
(`StudyEZ Agent` 의 `WakeToRun` 이 False).
"""
import ctypes
import sys
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
print("깨어 있게 잡았다 — 이 프로세스가 사는 동안만이다", flush=True)
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    pass
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    print("풀었다", file=sys.stderr)
