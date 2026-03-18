# M4 开发进度（交接快照）

生成时间：2026-03-18 23:27:18

## 核心结论
- M4-3 与 M4-4 已完成分离执行
- 主链路 1000 行 full 近3次可跑通
- 当前阻断状态：无 P0，存在 P2 告警
- ehydrated_text 已写入交付列

## 最近 1000 行 Full（最近3次）
|运行目录|run_id|verify|status|pass|P0|P1|P2|issues 文件|
|---|---|---|---|---|---:|---:|---:|---|
System.Object[]

## 当前状态要点
- un_smoke_pipeline.py: 连通->归一化->翻译->QA->重水化->verify 全链路已就绪
- smoke_verify.py: 已支持 manifest 驱动与 warn 闭环输出
- 	ranslate_llm.py: 支持 EN 主链路 + RU 回退，支持 long-text 标记与单行处理
- ehydrate_export.py: 关键修复已完成（token 映射参数对齐）
- M4_3/M4_4：脚本与决策报表已生成

## 注意
- 部分 run_manifest 字段版本不一致，建议以 smoke_verify_*.json 的 status/overall 做最终 PASS 判定。
