# Base image is built locally from python-build-standalone + host glibc —
# see docker/build_base_image.sh (container registries may be unreachable).
FROM qviqa-python:3.12

WORKDIR /app

# Dependencies are installed from pre-downloaded wheels so the build works
# with no network at all:  pip download -r requirements.txt -d docker/wheels
# The base image has no shell, so RUN must use exec form.
COPY docker/wheels /tmp/wheels
COPY requirements.txt ./
RUN ["python3", "-m", "pip", "install", "--no-cache-dir", "--no-index", \
     "--find-links", "/tmp/wheels", "-r", "requirements.txt"]
RUN ["python3", "-c", "import shutil; shutil.rmtree('/tmp/wheels')"]

COPY app ./app
COPY tests ./tests
COPY dev_run.py pyproject.toml ./

ENV DB_PATH=/data/qviqa.sqlite3 \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000
CMD ["python3", "-m", "app.main"]
