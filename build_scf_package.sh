#!/bin/bash
# 生成 SCF 部署包（zip），不实际部署
# 生成后可在 SCF 控制台手动上传：https://console.cloud.tencent.com/scf
set -e

OUTPUT="${1:-/tmp/quant-backend-scf.zip}"
cd "$(dirname "$0")/backend"

echo ">>> 安装依赖..."
TMPDIR=$(mktemp -d)
pip install -r requirements.txt -t "$TMPDIR" --quiet

echo ">>> 复制代码..."
cp -r app "$TMPDIR/"
cp -r westock "$TMPDIR/"
cp scf_bootstrap "$TMPDIR/"
cp run.py "$TMPDIR/" 2>/dev/null || true
rm -rf "$TMPDIR/__pycache__" "$TMPDIR/app/__pycache__" 2>/dev/null || true

echo ">>> 打包..."
cd "$TMPDIR"
zip -r "$OUTPUT" . -x "*.pyc" "*__pycache__*" > /dev/null
cd /
rm -rf "$TMPDIR"

echo "✅ 部署包已生成: $OUTPUT ($(ls -lh "$OUTPUT" | awk '{print $5}'))"
echo ""
echo "下一步："
echo "  1. 打开 https://console.cloud.tencent.com/scf"
echo "  2. 创建函数 → Web Function → 上传此 zip"
echo "  3. 环境变量设置参考 deploy_scf.sh"
