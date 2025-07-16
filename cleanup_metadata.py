#!/usr/bin/env python3
"""
清理无效的元数据记录
删除文件不存在但元数据还在的记录
"""

import json
import os

def cleanup_metadata():
    """清理无效的元数据记录"""
    metadata_file = 'uploads/file_metadata.json'
    
    if not os.path.exists(metadata_file):
        print("元数据文件不存在")
        return
    
    # 读取元数据
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    if not metadata:
        print("元数据为空")
        return
    
    print(f"开始清理元数据，原始记录数: {len(metadata)}")
    
    # 过滤掉文件不存在的记录
    valid_metadata = []
    removed_count = 0
    
    for item in metadata:
        file_path = item.get('file_path', '')
        
        # 将Docker路径转换为本地路径
        if file_path.startswith('/app/uploads/'):
            local_path = file_path.replace('/app/uploads/', 'uploads/')
        else:
            local_path = file_path
        
        # 检查文件是否存在
        if os.path.exists(local_path):
            valid_metadata.append(item)
            print(f"保留: {item.get('filename')} - 文件存在")
        else:
            removed_count += 1
            print(f"删除: {item.get('filename')} - 文件不存在 ({local_path})")
    
    # 保存清理后的元数据
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(valid_metadata, f, ensure_ascii=False, indent=2)
    
    print(f"清理完成！")
    print(f"原始记录数: {len(metadata)}")
    print(f"有效记录数: {len(valid_metadata)}")
    print(f"删除记录数: {removed_count}")

if __name__ == "__main__":
    cleanup_metadata() 