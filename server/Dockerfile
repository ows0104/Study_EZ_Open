# Cloud Run 하나. 워커도 스케줄러도 없다.
FROM python:3.13-slim

WORKDIR /srv

COPY studyez_contracts /studyez_contracts
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Cloud Run이 $PORT를 준다. 워커 하나로 충분하다 — 이 서버는 읽기만 하고
# 무거운 일은 전부 로컬에서 끝나 있다.
ENV PORT=8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
