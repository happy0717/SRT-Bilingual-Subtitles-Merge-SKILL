#!/usr/bin/env python3
"""
双语SRT字幕合并工具
将英文和中文字幕合并为"上中文下英文"的双语字幕格式
通过时间轴重叠进行智能匹配，而非简单拼接

用法:
    python merge_srt.py <英文srt> <中文srt> [输出srt]
    
    # 批量模式: 自动匹配目录下的 eng/chi 字幕对
    python merge_srt.py --batch <目录路径>
"""

import re
import sys
import os
import argparse
from pathlib import Path


def time_to_ms(t):
    """将 HH:MM:SS,mmm 转换为毫秒"""
    h, m, s_ms = t.split(':')
    s, ms = s_ms.split(',')
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def ms_to_time(ms):
    """将毫秒转换为 HH:MM:SS,mmm"""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(filepath):
    """解析SRT文件，返回条目列表"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        start = time_match.group(1)
        end = time_match.group(2)
        text = '\n'.join(lines[2:]).strip()

        entries.append({
            'index': index,
            'start': start,
            'end': end,
            'start_ms': time_to_ms(start),
            'end_ms': time_to_ms(end),
            'text': text,
        })

    return entries


def overlap_ratio(a_start, a_end, b_start, b_end):
    """计算两个时间区间的重叠比例（相对于较短的区间）"""
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_start >= overlap_end:
        return 0.0
    overlap_duration = overlap_end - overlap_start
    min_duration = min(a_end - a_start, b_end - b_start)
    if min_duration <= 0:
        return 0.0
    return overlap_duration / min_duration


def merge_srt(eng_file, chi_file, output_file, overlap_threshold=0.4):
    """
    合并英文和中文字幕
    策略:
      1. 以英文时间轴为基准
      2. 对每条英文字幕，找到时间重叠 >= threshold 的中文字幕
      3. 中文在上，英文在下
      4. 未被匹配的中文条目（如标题卡）也保留
    """
    eng_entries = parse_srt(eng_file)
    chi_entries = parse_srt(chi_file)

    print(f"英文条目: {len(eng_entries)}, 中文条目: {len(chi_entries)}")

    merged = []
    matched_chi_indices = set()

    for eng in eng_entries:
        matching_chi = []
        for i, chi in enumerate(chi_entries):
            ratio = overlap_ratio(
                eng['start_ms'], eng['end_ms'],
                chi['start_ms'], chi['end_ms']
            )
            if ratio >= overlap_threshold:
                matching_chi.append((i, chi))

        matching_chi.sort(key=lambda x: x[1]['start_ms'])

        for idx, _ in matching_chi:
            matched_chi_indices.add(idx)

        if matching_chi:
            chi_text = '\n'.join([c['text'] for _, c in matching_chi])
            merged_text = f"{chi_text}\n{eng['text']}"
        else:
            merged_text = eng['text']

        merged.append({
            'start': eng['start'],
            'end': eng['end'],
            'start_ms': eng['start_ms'],
            'text': merged_text,
        })

    # 添加未被匹配的中文条目（如片头标题卡、纯中文字幕）
    unmatched_chi = [chi for i, chi in enumerate(chi_entries) if i not in matched_chi_indices]
    for chi in unmatched_chi:
        merged.append({
            'start': chi['start'],
            'end': chi['end'],
            'start_ms': chi['start_ms'],
            'text': chi['text'],
        })

    # 按开始时间排序
    merged.sort(key=lambda x: x['start_ms'])

    # 去重：合并开始时间完全相同的条目（取内容更丰富的）
    deduped = []
    for entry in merged:
        if deduped and deduped[-1]['start_ms'] == entry['start_ms']:
            # 合并内容
            if entry['text'] not in deduped[-1]['text']:
                deduped[-1]['text'] = deduped[-1]['text'] + '\n' + entry['text']
        else:
            deduped.append(entry)

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        for i, entry in enumerate(deduped, 1):
            f.write(f"{i}\n")
            f.write(f"{entry['start']} --> {entry['end']}\n")
            f.write(f"{entry['text']}\n\n")

    matched_count = len(matched_chi_indices)
    print(f"匹配到的中文条目: {matched_count}/{len(chi_entries)}")
    print(f"未匹配的中文条目(独立保留): {len(unmatched_chi)}")
    print(f"合并后总条目: {len(deduped)}")
    print(f"输出文件: {output_file}")

    return len(deduped)


def find_pairs_in_directory(directory):
    """
    在目录中自动匹配 eng/chi 字幕对
    命名规则: 相同前缀 + _轨道N_[eng].srt / _轨道M_[chi].srt
    """
    dir_path = Path(directory)
    srt_files = sorted(dir_path.glob("*.srt"))

    eng_files = {}
    chi_files = {}

    for f in srt_files:
        name = f.stem
        if name.endswith('_[eng]'):
            prefix = name[:-len('_轨道X_[eng]')]
            # 提取共同前缀
            match = re.match(r'(.+)_轨道\d+_\[eng\]', name)
            if match:
                eng_files[match.group(1)] = f
        elif name.endswith('_[chi]'):
            match = re.match(r'(.+)_轨道\d+_\[chi\]', name)
            if match:
                chi_files[match.group(1)] = f

    pairs = []
    for prefix in sorted(eng_files.keys()):
        if prefix in chi_files:
            pairs.append((prefix, eng_files[prefix], chi_files[prefix]))

    return pairs


def batch_merge(directory, output_dir=None):
    """批量合并目录下的所有字幕对"""
    pairs = find_pairs_in_directory(directory)

    if not pairs:
        print("未找到匹配的 eng/chi 字幕对！")
        print("期望命名格式: XXX_轨道N_[eng].srt 和 XXX_轨道M_[chi].srt")
        return

    if output_dir is None:
        output_dir = os.path.join(directory, 'merged')
    os.makedirs(output_dir, exist_ok=True)

    print(f"找到 {len(pairs)} 对字幕，开始批量合并...\n")

    for prefix, eng_file, chi_file in pairs:
        episode_name = os.path.basename(prefix)
        output_file = os.path.join(output_dir, f"{episode_name}.bilingual.srt")
        print(f"--- {episode_name} ---")
        count = merge_srt(str(eng_file), str(chi_file), output_file)
        print()

    print(f"全部完成！合并后的字幕在: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='双语SRT字幕合并工具 - 上中文下英文格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单个文件合并
  python merge_srt.py episode_eng.srt episode_chi.srt output.srt

  # 批量合并目录下所有字幕对
  python merge_srt.py --batch ./That_90s_Show_S01_sub
        """
    )
    parser.add_argument('eng_file', nargs='?', help='英文SRT文件路径')
    parser.add_argument('chi_file', nargs='?', help='中文SRT文件路径')
    parser.add_argument('output_file', nargs='?', help='输出文件路径(默认: output.srt)')
    parser.add_argument('--batch', metavar='DIR', help='批量模式: 指定包含字幕文件的目录')
    parser.add_argument('--threshold', type=float, default=0.4,
                        help='时间重叠匹配阈值 (0.0-1.0, 默认0.4)')

    args = parser.parse_args()

    if args.batch:
        batch_merge(args.batch)
    elif args.eng_file and args.chi_file:
        output = args.output_file or 'output.srt'
        merge_srt(args.eng_file, args.chi_file, output, args.threshold)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
