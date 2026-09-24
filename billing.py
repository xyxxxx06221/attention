"""Provider-reported usage and DeepSeek balance; no inferred historical charges."""
from decimal import Decimal
import hashlib
import json
import threading
import time
from urllib.parse import urlsplit
import uuid


def account_id(settings):
    return hashlib.sha256((settings.get('base_url','').rstrip('/')+'\0'+settings.get('api_key','')).encode()).hexdigest()


def deepseek(settings):
    u = urlsplit(settings.get('base_url', ''))
    return u.scheme == 'https' and u.hostname == 'api.deepseek.com' and u.port in (None, 443) and not u.username and not u.password


def migrate(c, stamp):
    c.executescript('''CREATE TABLE IF NOT EXISTS api_usage(
    id TEXT PRIMARY KEY, account TEXT NOT NULL, model TEXT, created TEXT NOT NULL,
    prompt_tokens INTEGER, completion_tokens INTEGER, cached_tokens INTEGER, total_tokens INTEGER);
    CREATE INDEX IF NOT EXISTS idx_api_usage_account_created ON api_usage(account,created);
    ''')
    c.execute("INSERT OR IGNORE INTO metadata VALUES('api_usage_started',?)", (stamp,))


def record(db, settings, response, stamp):
    usage = response.get('usage') or {}
    def number(value):
        return value if type(value) is int and value >= 0 else None
    prompt, completion = number(usage.get('prompt_tokens')), number(usage.get('completion_tokens'))
    cached = number(usage.get('prompt_cache_hit_tokens', (usage.get('prompt_tokens_details') or {}).get('cached_tokens')))
    total = number(usage.get('total_tokens'))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    with db() as c:
        c.execute('INSERT INTO api_usage VALUES(?,?,?,?,?,?,?,?)',
                  (uuid.uuid4().hex, account_id(settings), str(response.get('model') or settings.get('model',''))[:200],
                   stamp, prompt, completion, cached, total))


class Balance:
    def __init__(self):
        self.lock = threading.Lock()
        self.account = None
        self.checked = 0
        self.value = None

    def get(self, settings, request, stamp, force=False):
        if not settings.get('api_key'):
            return {'status':'unconfigured', 'message':'尚未配置接口'}
        if not deepseek(settings):
            return {'status':'unsupported', 'message':'余额查询仅支持 DeepSeek 官方接口'}
        account = account_id(settings)
        with self.lock:
            if self.account != account:
                self.account, self.checked, self.value = account, 0, None
            age = time.monotonic() - self.checked
            ttl = 300 if self.value and self.value.get('status') == 'ok' else 60
            if self.value and age < (5 if force else ttl):
                return self.value.copy()
            try:
                raw, _ = request('https://api.deepseek.com/user/balance',
                                 headers={'Authorization':'Bearer '+settings['api_key']}, ai=True)
                result = json.loads(raw)
                balances = []
                for row in result['balance_infos']:
                    if row['currency'] not in ('CNY','USD'):
                        continue
                    safe = {'currency':row['currency']}
                    for field in ('total_balance','granted_balance','topped_up_balance'):
                        value = Decimal(str(row[field]))
                        if not value.is_finite() or value < 0:
                            raise ValueError('Invalid balance')
                        safe[field] = format(value, 'f')
                    balances.append(safe)
                if not balances:
                    raise ValueError('Missing balance')
                self.value = {'status':'ok', 'balances':balances, 'available':result.get('is_available') is True, 'updated_at':stamp}
            except Exception:
                previous = self.value or {}
                self.value = {'status':'error', 'message':'余额暂时无法更新，请稍后重试',
                              'balances':previous.get('balances', []), 'updated_at':previous.get('updated_at')}
            self.checked = time.monotonic()
            return self.value.copy()


def summary(db, settings, now):
    day = now.date().isoformat()
    result = {}
    with db() as c:
        started = c.execute("SELECT value FROM metadata WHERE key='api_usage_started'").fetchone()
        for key, since in [('today', day), ('month', day[:7]+'-01'), ('all', '')]:
            r = c.execute('''SELECT count(*) AS calls, count(total_tokens) AS measured_calls,
            coalesce(sum(prompt_tokens),0) AS prompt_tokens, coalesce(sum(completion_tokens),0) AS completion_tokens,
            coalesce(sum(cached_tokens),0) AS cached_tokens, coalesce(sum(total_tokens),0) AS total_tokens
            FROM api_usage WHERE account=? AND created>=?''', (account_id(settings), since)).fetchone()
            result[key] = dict(r)
    return {'started_at':started[0] if started else None, 'usage':result,
            'provider':'DeepSeek' if deepseek(settings) else '当前接口',
            'scope':'仅统计本软件自启用记录以来收到的接口用量，不是账户全部历史账单。'}
