from datetime import datetime

from flask import Flask, jsonify, request
import random

app = Flask(__name__)


@app.route('/data', methods=['GET'])
def get_data():
    # 1. 解析查询参数
    start_time = request.args.get('startTime')  # 单值参数，字符串格式 :contentReference[oaicite:0]{index=0}
    end_time = request.args.get('endTime')  # 同上 :contentReference[oaicite:1]{index=1}
    tag_names = request.args.getlist('tagNames[]')  # 多值参数，列表，使用 getlist :contentReference[oaicite:2]{index=2}
    data_num = request.args.get('dataNum', type=int, default=10)  # 数值型，可指定类型和默认值 :contentReference[oaicite:3]{index=3}

    # 2. 简单校验
    if not (start_time and end_time and tag_names):
        return jsonify({
            "result": None,
            "success": False,
            "__abp": True,
            "error": "缺少必填参数",
            "targetUrl": "",
            "unAuthorizedRequest": False
        }), 400

    # 3. 构造模拟返回数据
    items = []
    # 将时间字符串解析为 datetime 方便生成不同时间点
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        t0 = datetime.strptime(start_time, fmt)
        t1 = datetime.strptime(end_time, fmt)
    except ValueError:
        return jsonify({
            "result": None,
            "success": False,
            "__abp": True,
            "error": "时间格式应为 YYYY-MM-DD HH:MM:SS",
            "targetUrl": "",
            "unAuthorizedRequest": False
        }), 400

    for name in tag_names:
        # 等距生成 data_num 条记录
        delta = (t1 - t0) / max(data_num - 1, 1)
        values = []
        for i in range(data_num):
            ts = (t0 + delta * i).strftime(fmt)
            values.append({
                "timeStamp": ts,
                "valueState": 1,
                # 随机示例值
                "value": round(random.uniform(20.0, 100.0), 6)
            })
        items.append({
            "name": name,
            "value": values
        })

    # 4. 返回结果
    return jsonify({
        "result": {
            "items": items
        },
        "success": True,
        "__abp": True,
        "error": "",
        "targetUrl": "",
        "unAuthorizedRequest": False
    })


@app.route('/devName', methods=['GET'])
def get_dev_name():
    data = {
        "data": [
            {
                "id": "dev001",
                "name": "设备A",
                "children": []
            },
            {
                "id": "dev002",
                "name": "设备B",
                "children": []
            },
            {
                "id": "dev003",
                "name": "设备C",
                "children": []
            }
        ]
    }
    return jsonify(data)


@app.route('/point', methods=['GET'])
def get_point():
    data = {
        "data": [
            {
                "devNo": "dev001",
                "paramValues": "dev001.point1;dev001.point2;dev001.point3",
                "paramNames": "温度;压力;流量",
                "configName": random.choice(["温度", "压力", "流量"])
            },
            {
                "devNo": "dev002",
                "paramValues": "dev002.point4;dev002.point5;dev002.point6",
                "paramNames": "温度;压力;流量",
                "configName": random.choice(["温度", "压力", "流量"])
            },
            {
                "devNo": "dev003",
                "paramValues": "dev003.point7;dev003.point8;dev003.point1",
                "paramNames": "温度;压力;流量",
                "configName": random.choice(["温度", "压力", "流量"])
            }
        ]
    }
    return jsonify(data)


if __name__ == '__main__':
    app.run(port=8500)
