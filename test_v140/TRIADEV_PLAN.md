# TriadDev: Loc-MVR v1.4.0 完整测试实施计划

**Date**: 2026-02-24  
**Status**: 50行测试成功 ✅ (Score: 87.5/100)  
**Next**: 500行完整测试

---

## 测试结果摘要

### 50行测试成功 ✅
```
Score: 87.5/100
Missing Rate: 20.0%
Escalation: 0.0%
Parse Errors: 20.0%
Avg Latency: 36369ms (36.4秒)
P95 Latency: ~60秒
```

**问题识别**:
- 20% Parse Errors - 需要调整超时参数
- 平均延迟 36秒/batch - 需要更长超时时间

---

## Phase 1: 优化超时参数 ⏳ READY

### 任务 1.1: 分析当前超时设置
- 检查 `run_validation.py` 中的超时参数
- 检查 `runtime_adapter.py` 中的默认超时

### 任务 1.2: 调整超时参数
- 将 batch 超时从默认 60s 调整到 120s
- 将 API 调用超时从 60s 调整到 90s
- 添加重试机制

### 任务 1.3: 测试优化后的 50行
- 验证 parse error 是否减少
- 验证整体稳定性

---

## Phase 2: 500行长任务 ⏳ READY

### 任务 2.1: 配置 screen/tmux
- 创建持久会话
- 配置日志记录
- 设置自动监控

### 任务 2.2: 启动 500行测试
- 使用优化后的参数
- 在 screen 会话中运行
- 实时进度记录

### 任务 2.3: 完成后续 Pipeline
- QA Hard
- QA Soft
- Autopromote
- Refresh

---

## 执行计划

```
Phase 1 (30分钟)
  ├── 1.1 分析超时 (10分钟)
  ├── 1.2 调整参数 (10分钟)
  └── 1.3 测试验证 (10分钟)

Phase 2 (90-120分钟)
  ├── 2.1 配置 screen (10分钟)
  ├── 2.2 启动 500行 (90分钟)
  └── 2.3 后续 Pipeline (20分钟)
```

---

**Status**: 🚀 **Ready to Start Phase 1**