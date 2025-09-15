#!/bin/bash

echo "=== 服务器资源使用情况检查 ==="
echo ""

# 内存使用情况
echo "【内存使用情况】"
free -h
echo ""

# CPU使用情况
echo "【CPU使用情况】"
top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "CPU使用率: " 100 - $1 "%"}'
echo ""

# 磁盘使用情况
echo "【磁盘使用情况】"
df -h
echo ""

# GPU使用情况（如果有NVIDIA GPU）
if command -v nvidia-smi &> /dev/null; then
    echo "【GPU使用情况】"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
    echo ""
fi

# 当前运行的高资源消耗进程
echo "【高资源消耗进程（按内存排序）】"
ps aux --sort=-%mem | head -10
echo ""

echo "【高资源消耗进程（按CPU排序）】"
ps aux --sort=-%cpu | head -10
echo ""

# 网络连接数
echo "【网络连接数】"
ss -tuln | wc -l
echo ""

# 系统负载
echo "【系统负载】"
uptime
echo ""

# 建议
echo "=== 部署建议 ==="
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
USED_MEM=$(free -m | awk '/^Mem:/{print $3}')
AVAILABLE_MEM=$(free -m | awk '/^Mem:/{print $7}')

echo "总内存: ${TOTAL_MEM}MB"
echo "已用内存: ${USED_MEM}MB" 
echo "可用内存: ${AVAILABLE_MEM}MB"
echo ""

if [ $AVAILABLE_MEM -gt 20480 ]; then
    echo "✅ 内存充足，可以部署10个应用实例"
elif [ $AVAILABLE_MEM -gt 10240 ]; then
    echo "⚠️  内存适中，建议部署5个应用实例"
elif [ $AVAILABLE_MEM -gt 5120 ]; then
    echo "⚠️  内存紧张，建议部署2-3个应用实例"
else
    echo "❌ 内存不足，不建议与模型训练同时运行"
fi

# CPU核心数
CPU_CORES=$(nproc)
echo "CPU核心数: $CPU_CORES"

if [ $CPU_CORES -ge 16 ]; then
    echo "✅ CPU核心充足，可以与模型训练并行"
elif [ $CPU_CORES -ge 8 ]; then
    echo "⚠️  CPU核心适中，建议错峰使用"
else
    echo "❌ CPU核心不足，建议单独运行"
fi