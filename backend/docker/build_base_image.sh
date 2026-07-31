#!/usr/bin/env bash
# Builds the qviqa-python base image WITHOUT any container registry access.
#
# Why: some build environments (including the sandbox this project was ported
# in) block Docker Hub / ghcr / ECR blob CDNs, so `FROM python:3.12-slim` can't
# be pulled. This script assembles a minimal rootfs from:
#   * python-build-standalone (self-contained CPython, fetched from GitHub
#     releases or provided locally via $PYTHON_TARBALL), and
#   * the host's glibc runtime libraries (resolved with ldd),
# then feeds it to `docker import`.
#
# Usage:  PYTHON_TARBALL=/path/to/cpython-*.tar.gz ./build_base_image.sh
#         (or let it download the default build)
set -euo pipefail

IMAGE_TAG="${IMAGE_TAG:-qviqa-python:3.12}"
PY_VERSION="20250712/cpython-3.12.11%2B20250712-x86_64-unknown-linux-gnu-install_only.tar.gz"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_VERSION}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ROOTFS="$WORK/rootfs"
mkdir -p "$ROOTFS"/{opt,etc/ssl/certs,tmp,usr/bin,app,data}

tarball="${PYTHON_TARBALL:-}"
if [[ -z "$tarball" ]]; then
    tarball="$WORK/python.tar.gz"
    echo "==> downloading python-build-standalone"
    curl -fSL -o "$tarball" "$PY_URL"
fi
echo "==> extracting python to /opt/python"
tar -xzf "$tarball" -C "$ROOTFS/opt"
mv "$ROOTFS/opt/python" "$ROOTFS/opt/python" 2>/dev/null || true

echo "==> copying host glibc runtime for the interpreter"
copy_with_path() {
    local src="$1"
    [[ -e "$src" ]] || return 0
    mkdir -p "$ROOTFS/$(dirname "$src")"
    cp -Ln "$src" "$ROOTFS/$src" 2>/dev/null || true
}
BIN="$ROOTFS/opt/python/bin/python3"
for lib in $(ldd "$BIN" | awk '{for(i=1;i<=NF;i++) if ($i ~ /^\//) print $i}' | sort -u); do
    copy_with_path "$lib"
done
# libs loaded lazily by the stdlib (_ssl, _sqlite3, zlib и т.д.)
for extra in libssl.so.3 libcrypto.so.3 libz.so.1 libbz2.so.1.0 liblzma.so.5 \
             libsqlite3.so.0 libffi.so.8 libuuid.so.1 libcrypt.so.1 \
             libnss_dns.so.2 libnss_files.so.2 libresolv.so.2; do
    for dir in /lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu /lib64 /usr/lib64; do
        copy_with_path "$dir/$extra"
    done
done

echo "==> CA certificates and minimal /etc"
cp /etc/ssl/certs/ca-certificates.crt "$ROOTFS/etc/ssl/certs/" 2>/dev/null || \
    cp /etc/pki/tls/certs/ca-bundle.crt "$ROOTFS/etc/ssl/certs/ca-certificates.crt"
cat > "$ROOTFS/etc/passwd" <<'EOF'
root:x:0:0:root:/root:/bin/false
app:x:1000:1000:app:/app:/bin/false
EOF
cat > "$ROOTFS/etc/group" <<'EOF'
root:x:0:
app:x:1000:
EOF
echo "hosts: files dns" > "$ROOTFS/etc/nsswitch.conf"
ln -sf /opt/python/bin/python3 "$ROOTFS/usr/bin/python3"
chmod 1777 "$ROOTFS/tmp"

echo "==> docker import -> $IMAGE_TAG"
tar -C "$ROOTFS" -c . | docker import \
    -c 'ENV PATH=/opt/python/bin:/usr/bin:/bin SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt' \
    -c 'WORKDIR /app' \
    - "$IMAGE_TAG"
docker run --rm "$IMAGE_TAG" python3 -c 'import ssl, sqlite3, zlib, sys; print("base image OK:", sys.version)'
