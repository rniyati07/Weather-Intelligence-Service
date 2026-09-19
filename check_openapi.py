import sys

sys.path.insert(0, r'c:\Users\Niyati\Downloads\Weather_Intelligence_service')
from app.main import create_app

app = create_app()
schema = app.openapi()
for path in ['/api/v1/conversations', '/api/v1/conversations/{conversation_id}', '/api/v1/conversations/chat']:
    if path in schema['paths']:
        for method, op in schema['paths'][path].items():
            print(f'{method.upper()} {path}: responses = {list(op.get("responses", {}).keys())}')
            for status in ['200', '201']:
                if status in op.get('responses', {}):
                    resp = op['responses'][status]
                    print(f'  {status} response: {resp}')
                    if 'content' in resp and 'application/json' in resp['content']:
                        ref = resp['content']['application/json']['schema'].get('$ref')
                        if ref:
                            print(f'  {status} -> {ref}')