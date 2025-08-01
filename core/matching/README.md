# 个体选配模块说明

## 模块结构

### 核心文件（当前使用）

1. **cycle_based_matcher.py** ⭐
   - 当前主要的选配分配器
   - 基于周期的分配策略，严格按照周期顺序和冻精比例分配
   - 支持最小分配保证（小库存公牛至少1头）
   - 被 `main_window.py` 中的选配分配功能使用

2. **matrix_recommendation_generator.py** ⭐
   - 主要的推荐生成器
   - 生成完整的配对矩阵（所有母牛×所有公牛）
   - 计算近交系数、隐性基因检查、后代得分
   - 被 `recommendation_worker.py` 使用

3. **allocation_utils.py**
   - 分配工具函数
   - 提供按比例分配和平均分配功能
   - 支持最小分配保证

4. **models.py**
   - 领域模型定义
   - 包含 Cow、Bull、PairingResult 等实体

5. **group_preview_updater.py**
   - 分组预览更新工具
   - 更新显示每个分组的未分配数量

### 备选组件

6. **simple_recommendation_generator.py**
   - 简化版的推荐生成器
   - 作为备选方案，处理简单场景
   - 被 `simple_recommendation_worker.py` 使用

### 废弃文件

- **individual_matcher.py** ⚠️ DEPRECATED
  - 个体选配的早期实现
  - 功能已被 cycle_based_matcher.py 完全替代
  - 仅保留用于向后兼容

- **matching_worker.py** ⚠️ DEPRECATED
  - 使用废弃的 individual_matcher
  - 主窗口现在直接使用 cycle_based_matcher

- **recommendation_generator.py** ⚠️ DEPRECATED
  - 早期版本，已被 matrix_recommendation_generator 替代

### 已删除的文件

- **individual_matcher_v2.py** - 旧版本
- **individual_matcher_v3.py** - 旧版本
- **recommendation_generator_v2.py** - 旧版本

## 主要工作流程

### 1. 推荐生成阶段
```
用户点击"生成选配推荐" 
→ RecommendationWorker 
→ MatrixRecommendationGenerator
→ 生成配对矩阵和推荐汇总
→ 保存到 individual_mating_matrices.xlsx 和 individual_mating_report.xlsx
```

### 2. 选配分配阶段
```
用户点击"选配分配"
→ 收集选中的组和冻精库存
→ CycleBasedMatcher
→ 按周期和库存比例分配
→ 保存到 individual_allocation_result.xlsx
```

## 下一步改进计划

1. **统一接口**：将 individual_matcher.py 的功能迁移到 cycle_based_matcher.py
2. **删除废弃文件**：清理 matcher.py、allocator.py、recommendation_generator.py
3. **优化数据流**：减少对多个Excel文件的依赖
4. **改进架构**：引入领域模型，实现策略模式