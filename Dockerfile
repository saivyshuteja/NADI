FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY data ./data
COPY tests ./tests
RUN pip install --no-cache-dir -e .
ENV NADI9_MODE=mock
CMD ["python", "-m", "nadi9", "--mode", "mock"]
