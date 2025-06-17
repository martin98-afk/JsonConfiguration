"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: versions.py
@time: 2025/6/17 09:31
@desc: 
"""
import json
import os

release_list = [{
    "version": "1.0.1",
    "publishDate": "2023-07-07 10:00",
    "forceUpdate": True,
    "publishNotes": ["1. 版本更新", "2. 版本1.0.1", "3. 更新内容：xxxx"],
    "updateUrl": f'{config.INTERNAL_DOWNLOAD_URL}/app.1.0.1.20230707.zip'
}, {
    "version": "1.0.0",
    "publishDate": "2023-07-05 17:00",
    "forceUpdate": True,
    "publishNotes": ["1. 初始版本", "2. 生成1.0.0", "3. 更新内容：xxxx"],
    "updateUrl": f'{config.INTERNAL_DOWNLOAD_URL}/app.1.0.0.20230705.zip'
}]

current_version = release_list[0]['version']

def generate_version_json(dist_path):
    versions_json = json.dumps(release_list, indent=4, ensure_ascii=False)
    if not os.path.exists(dist_path):
        os.mkdir(dist_path)
    with open(os.path.join(dist_path, 'versions.json'), 'w', encoding="utf8") as json_file:
        json_file.write(versions_json)
