import re


def list2str(value: list) -> str:
    """将配置中的list形式用清晰的形式展现在配置工具中"""
    if len(value) > 0 and isinstance(value[0], list):
        value = "\n".join([" ~ ".join([str(v) for v in item]) for item in value])
    elif len(value) > 0:
        value = " ~ ".join([str(v) for v in value])
    elif len(value) == 0:
        value = ""

    return value


def str2list(value: str) -> list:
    """将配置工具中的多行配置转为list格式存储"""
    if "\n" in value and re.search(" ~ ", value):
        value = [item.split(" ~ ") for item in value.split("\n")]
    elif re.search(" ~ ", value):
        value = value.split(" ~ ")
    elif value == "":
        value = []

    return value
