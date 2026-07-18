#!/bin/bash
# ============================================================
# 部署量化平台后端到腾讯云函数（SCF Web Function）
#
# 用法：
#   export SECRET_ID="你的腾讯云 SecretId"
#   export SECRET_KEY="你的腾讯云 SecretKey"
#   bash deploy_scf.sh
#
# 或直接运行后按提示输入
# ============================================================
set -e

echo "=========================================="
echo "  量化平台 → 腾讯云函数(SCF) 一键部署"
echo "=========================================="

# ---------- 1. 凭据 ----------
if [ -z "$SECRET_ID" ]; then
  read -p "腾讯云 SecretId: " SECRET_ID
fi
if [ -z "$SECRET_KEY" ]; then
  read -sp "腾讯云 SecretKey: " SECRET_KEY
  echo ""
fi

REGION="${REGION:-ap-guangzhou}"
FUNCTION_NAME="${FUNCTION_NAME:-quant-backend}"
ZIP_FILE="/tmp/quant-backend-scf.zip"

# ---------- 2. 打包 ----------
echo ""
echo ">>> 打包部署包..."
cd "$(dirname "$0")/backend"

TMPDIR=$(mktemp -d)
pip install -r requirements.txt -t "$TMPDIR" --quiet

cp -r app "$TMPDIR/"
cp -r westock "$TMPDIR/"
cp scf_bootstrap "$TMPDIR/"
cp run.py "$TMPDIR/" 2>/dev/null || true
rm -rf "$TMPDIR/__pycache__" "$TMPDIR/app/__pycache__" 2>/dev/null || true

cd "$TMPDIR"
zip -r "$ZIP_FILE" . -x "*.pyc" "*__pycache__*" > /dev/null
cd /
rm -rf "$TMPDIR"
echo "   打包完成: $(ls -lh "$ZIP_FILE" | awk '{print $5}')"

# ---------- 3. 创建/更新函数 ----------
echo ""
echo ">>> 部署到 SCF（首次创建约 30s）..."

BASE64_ZIP=$(base64 -w0 < "$ZIP_FILE")

# 检查函数是否已存在
EXIST=$(curl -s -H "Authorization: TC3-HMAC-SHA256 ..." \
  "https://scf.tencentcloudapi.com/?Action=ListFunctions&Region=$REGION" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(1 if any(f['FunctionName']=='$FUNCTION_NAME' for f in d.get('Response',{}).get('Functions',[])) else 0)" 2>/dev/null || echo "0")

if [ "$EXIST" = "1" ]; then
  echo "   函数已存在，更新代码..."
  tccli scf UpdateFunctionCode \
    --region "$REGION" \
    --FunctionName "$FUNCTION_NAME" \
    --Code "ZipFile=$BASE64_ZIP" \
    --Handler scf_bootstrap \
    --Runtime CustomRuntime
else
  echo "   创建新函数..."
  tccli scf CreateFunction \
    --region "$REGION" \
    --FunctionName "$FUNCTION_NAME" \
    --Code "ZipFile=$BASE64_ZIP" \
    --Type Web \
    --Description "AI量化交易平台后端" \
    --Timeout 30 \
    --MemorySize 512 \
    --Environment '{
      "Variables": {
        "CORS_ALLOW_ORIGINS": "*",
        "DATA_CACHE_TTL": "30",
        "WESTOCK_SCRIPT": "/var/user/westock/index.js",
        "NODE_BIN": "/tmp/node/bin/node",
        "PYTHONUNBUFFERED": "1"
      }
    }'
fi

# ---------- 4. 获取访问地址 ----------
echo ""
echo ">>> 获取函数访问地址..."
sleep 5
# Web Function 的访问地址格式：https://<serviceId>-<ap-guangzhou>.apigw.tencentcs.com
TRIGGER_URL=$(tccli scf GetFunction \
  --region "$REGION" \
  --FunctionName "$FUNCTION_NAME" \
  --query 'Function.Triggers[0].TriggerDesc' \
  --output text 2>/dev/null | python3 -c "
import sys,json
try:
    t=json.load(sys.stdin)
    print(f'https://{t.get(\"serviceId\",\"?\")}-{t.get(\"subDomain\",\"?\")}.apigw.tencentcs.com')
except: print('')
" 2>/dev/null)

if [ -n "$TRIGGER_URL" ]; then
  echo "   ✅ 访问地址: $TRIGGER_URL"
  echo ""
  echo "=========================================="
  echo "  部署完成！"
  echo "  下一步：用此 URL 重建前端："
  echo "    NEXT_PUBLIC_API_BASE=$TRIGGER_URL"
  echo "    npm run build & push gh-pages"
  echo "=========================================="
else
  echo "   ⚠️ 请到 SCF 控制台查看触发器生成的访问地址"
  echo "     https://console.cloud.tencent.com/scf"
fi

# 清理
rm -f "$ZIP_FILE"
