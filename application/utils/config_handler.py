import json
import os
import configparser
import yaml

from datetime import datetime

from application.utils.utils import error_catcher_decorator

PATH_PREFIX = './configurations/'
FILE_FILTER = "JSON 文件 (*.json);;YAML 文件 (*.yaml *.yml);;INI 文件 (*.ini)"
os.makedirs(PATH_PREFIX, exist_ok=True)
HISTORY_PATH = os.path.expanduser(os.path.join(PATH_PREFIX, "历史版本记录.json"))


def path_exists(path):
    return os.path.exists(os.path.join(PATH_PREFIX, path))


def load_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        if file_path.endswith('.json'):
            return json.load(file)
        elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
            return yaml.safe_load(file)
        elif file_path.endswith('.ini'):
            config = configparser.ConfigParser()
            config.read_file(file)
            return {section: dict(config[section]) for section in config.sections()}
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

@error_catcher_decorator
def save_config(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as file:
        if file_path.endswith('.json'):
            json.dump(data, file, ensure_ascii=False, indent=4)
        elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
            yaml.dump(data, file, allow_unicode=True, default_flow_style=False)
        elif file_path.endswith('.ini'):
            config = configparser.ConfigParser()
            for section, values in data.items():
                config[section] = values
            config.write(file)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

def save_history(path, config):
    history = []
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except:
                history = []
    history.append(
        [
            os.path.basename(path).replace(".json", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            config,
        ]
    )

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
