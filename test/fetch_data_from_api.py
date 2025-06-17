"""
@author: mading
@license: (C) Copyright: LUCULENT Corporation Limited.
@contact: mading@luculent.net
@file: fetch_data_from_api.py
@time: 2025/4/23 14:41
@desc: 
"""
import datetime

import httpx
import numpy as np

#
def fetch_data_from_api(tag_name, start_time, end_time):
    """从API获取数据"""
    params = {
        "span": 2,
        "dataMode": 3,
        "startTime": start_time,
        "endTime": end_time,
        "tagNames[]": tag_name
    }

    try:
        with httpx.Client(base_url="http://172.16.134.122:8900") as client:
            response = client.get(
                url="/rest/database/sis/getSeriesValuesByNameList",
                params=params,
                timeout=10
            )
        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                items = data["result"]["items"]
                if items:
                    points = items[0]["value"]
                    times = [datetime.datetime.strptime(p["timeStamp"], "%Y-%m-%d %H:%M:%S").timestamp() for p in points]
                    values = [p["value"] for p in points]
                    return np.array(times), np.array(values)
        return None, None
    except Exception as e:
        print(f"数据获取失败: {str(e)}")
        return None, None



if __name__ == "__main__":
    data1, data2 = fetch_data_from_api("AN_LK_QT_FJ_16_34", "2025-04-23 10:00:00", "2025-04-23 12:00:00")