# Python 3.9 베이스 이미지 사용
FROM python:3.9-slim

# 작업 디렉토리 생성
WORKDIR /app

# 필요한 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY shibboleth_exporter.py .

# 포트 노출 (기본값 9090)
EXPOSE 9090

# 환경 변수 설정 (기본값)
ENV PORT=9090
ENV METRICS_ENDPOINT="https://localhost/idp/profile/admin/metrics"

# 실행 명령
CMD ["python", "shibboleth_exporter.py"]

