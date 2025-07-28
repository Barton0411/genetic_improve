"""
版本信息管理
"""

# 版本号格式: 主版本号.次版本号.修订号
VERSION = "1.0.0"

# 版本历史
VERSION_HISTORY = [
    {
        "version": "1.0.0",
        "date": "2025-07-28",
        "author": "Development Team",
        "changes": [
            "初始版本发布",
            "实现育种项目管理功能",
            "实现数据上传功能（母牛、公牛、配种记录、体型外貌、基因组数据）",
            "实现关键育种性状分析",
            "实现牛只指数计算排名",
            "实现近交系数及隐性基因分析",
            "实现个体选配功能",
            "实现选配推荐报告生成（包含后代得分预测）",
            "实现PPT自动报告生成",
            "集成阿里云数据库",
            "优化UI界面和用户体验"
        ]
    }
]

# 获取当前版本
def get_version():
    """获取当前版本号"""
    return VERSION

# 获取版本信息
def get_version_info():
    """获取完整版本信息"""
    if VERSION_HISTORY:
        return VERSION_HISTORY[0]
    return None

# 获取版本历史
def get_version_history():
    """获取所有版本历史"""
    return VERSION_HISTORY