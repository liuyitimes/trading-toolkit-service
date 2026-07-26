import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app


def test_contract_endpoints_match_flask_routes():
    contract_path = Path(__file__).resolve().parents[2] / 'contracts' / 'http-api.json'
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    routes = {
        (re.sub(r'<(?:[^:<>]+:)?([^<>]+)>', r':\1', rule.rule), method)
        for rule in backend_app.app.url_map.iter_rules()
        for method in rule.methods - {'HEAD', 'OPTIONS'}
    }

    missing = [
        endpoint
        for endpoint in contract['endpoints']
        if (endpoint['path'], endpoint['method']) not in routes
    ]

    assert missing == []
