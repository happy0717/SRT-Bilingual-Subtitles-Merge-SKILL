---
name: "srt-bilingual-merge"
description: "Merge English and Chinese SRT subtitle files into bilingual format (Chinese top, English bottom). Invoke when user wants to merge dual-language subtitles, create bilingual subtitles from separate SRT files, or batch-merge subtitle pairs in a directory."
---

# SRT Bilingual Merge

合并英文和中文字幕为双语字幕（上中文下英文格式），通过时间轴重叠进行智能匹配。

## 核心脚本

脚本位置: `scripts/merge_srt.py` (在字幕目录中)

## 使用方式

### 单个文件合并
```bash
python scripts/merge_srt.py <英文srt> <中文srt> [输出srt]
```

### 批量合并（推荐）
```bash
python scripts/merge_srt.py --batch <字幕目录>
```

批量模式会自动识别目录中成对的 `_[eng].srt` 和 `_[chi].srt` 文件，输出到 `merged/` 子目录。

### 调整匹配阈值
```bash
python scripts/merge_srt.py <英文srt> <中文srt> output.srt --threshold 0.5
```

## 文件命名规范

脚本通过以下模式识别字幕对:
- 英文: `*_轨道N_[eng].srt`
- 中文: `*_轨道M_[chi].srt`

例如:
- `That.90s.Show.S01E01_轨道4_[eng].srt`
- `That.90s.Show.S01E01_轨道35_[chi].srt`

## 合并策略

1. 以英文时间轴为基准
2. 通过时间重叠比例（默认40%）匹配中文字幕
3. 中文文本在上、英文文本在下
4. 未匹配的中文条目（如标题卡、专属翻译）独立保留
5. 未匹配的英文条目（如音效标注 `[music playing]`）独立保留

## 输出格式

```
序号
开始时间 --> 结束时间
中文文本
英文文本
```

例如:
```
9
00:00:36,202 --> 00:00:37,287
你好香
You smell good.
```
