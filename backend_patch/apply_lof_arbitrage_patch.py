# -*- coding: utf-8 -*-
"""应用 LOF 套利预测后端补丁

用途：
1. 验证 services/lof_arbitrage.py 已存在于后端
2. 修复 app.py 顶部 import（确保 get_arbitrage_prediction 被引用）
3. 重启后端（提示）

用法：py apply_lof_arbitrage_patch.py
"""
import os
import re
import sys

BACKEND = r'd:\Develop\GitHub\trading-toolkit-service\cloudrun'


def step1_verify_service_file():
    """验证 lof_arbitrage.py 已存在"""
    f = os.path.join(BACKEND, 'services', 'lof_arbitrage.py')
    if not os.path.exists(f):
        print(f'[ERROR] {f} 不存在，请先通过 Write 工具创建')
        sys.exit(1)
    print(f'[OK] 1/3 lof_arbitrage.py 已存在 ({os.path.getsize(f)} bytes)')


def step2_fix_app_imports():
    """修复 app.py 顶部 import：添加 get_arbitrage_prediction"""
    f = os.path.join(BACKEND, 'app.py')
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()

    if 'get_arbitrage_prediction as _get_lof_arbitrage_prediction' in content:
        print('[SKIP] 2/3 app.py 已包含 lof_arbitrage import（alias 形式）')
        return

    import_block = 'from services.lof_arbitrage import get_arbitrage_prediction as _get_lof_arbitrage_prediction\n'
    # 在 utils.response 前插入（确保能找到 import 锚点）
    new_content = content.replace(
        'from utils.response import api_response',
        import_block + 'from utils.response import api_response',
        1,
    )

    if new_content == content:
        print('[ERROR] 2/3 未匹配到 utils.response import 锚点')
        return

    # 替换函数调用为别名调用
    new_content = new_content.replace(
        '        result = get_arbitrage_prediction(',
        '        result = _get_lof_arbitrage_prediction(',
    )

    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(new_content)
    print('[OK] 2/3 app.py 顶部 import 修复完成')


def step3_verify_routes():
    """验证两个 API 路由已注册"""
    f = os.path.join(BACKEND, 'app.py')
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()

    has_share = '/api/v1/lof/<code>/share-history' in content
    has_predict = '/api/v1/lof/<code>/arbitrage-predict' in content

    if has_share and has_predict:
        print('[OK] 3/3 两个 API 路由已注册')
    else:
        print(f'[WARN] 3/3 路由缺失: share-history={has_share}, arbitrage-predict={has_predict}')


def main():
    print(f'==> 应用 LOF 套利预测补丁到: {BACKEND}\n')
    if not os.path.isdir(BACKEND):
        print(f'[ERROR] 后端目录不存在: {BACKEND}')
        sys.exit(1)
    step1_verify_service_file()
    step2_fix_app_imports()
    step3_verify_routes()
    print('\n==> 补丁应用完成! 请重启后端：')
    print('   1. 停止当前后端进程 (Ctrl+C)')
    print('   2. cd d:\\Develop\\GitHub\\trading-toolkit-service')
    print('   3. py cloudrun\\app.py')
    print()
    print('==> 测试 API:')
    print('   curl "http://localhost:8080/api/v1/lof/161725/arbitrage-predict?amount=100&premium=5"')


if __name__ == '__main__':
    main()
