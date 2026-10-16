"""Jules REST API одной командой: поставить задачу, дождаться, забрать дифф, ответить в задачу.

Ключ — переменная окружения JULES_API_KEY (Jules → Settings → API Key; не больше 3 ключей). Только стандартная библиотека.

    python3 -X utf8 jules.py sources                                  подключённые репозитории
    python3 -X utf8 jules.py new <owner/repo> <файл ТЗ> [--branch main] [--title "…"] [--no-pr] [--plan]
    python3 -X utf8 jules.py status <id>                              состояние и выходы (PR)
    python3 -X utf8 jules.py wait <id> [--minutes 70]                 ждать COMPLETED / FAILED / AWAITING_* / PAUSED
    python3 -X utf8 jules.py log <id> [--all]                         журнал шагов (последние 30 или все; страницы — от старых к новым)
    python3 -X utf8 jules.py patch <id> <файл.patch>                  сохранить итоговый дифф
    python3 -X utf8 jules.py say <id> <файл сообщения>                сообщение в идущую задачу (правки при приёмке)
    python3 -X utf8 jules.py approve <id>                             одобрить план (задача создана с --plan)

Код выхода: 0 — ок, 1 — ошибка API или задача FAILED, 2 — не дождались.
"""
import json, os, sys, time, urllib.error, urllib.request

BASE = 'https://jules.googleapis.com/v1alpha/'
DONE = ('COMPLETED', 'FAILED', 'PAUSED', 'AWAITING_PLAN_APPROVAL', 'AWAITING_USER_FEEDBACK')


def call(path, body=None, method=None):
    key = os.environ.get('JULES_API_KEY')
    if not key:
        sys.exit('нет JULES_API_KEY в окружении')
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 method=method or ('GET' if body is None else 'POST'),
                                 headers={'X-Goog-Api-Key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code}: {e.read().decode()[:500]}')
    return json.loads(raw) if raw.strip() else {}


def sid(x):
    return x if x.startswith('sessions/') else 'sessions/' + x


def arg(args, name, default=None):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default


def flag(args, name):
    if name in args:
        args.remove(name); return True
    return False


def outputs(s):
    for o in s.get('outputs', []):
        if 'pullRequest' in o:
            print('PR:', o['pullRequest'].get('url'), '—', o['pullRequest'].get('title'))
        if 'changeSet' in o:
            p = o['changeSet'].get('gitPatch', {}).get('unidiffPatch', '')
            files = [l.split(' b/', 1)[-1] for l in p.splitlines() if l.startswith('diff --git')]
            print('файлы:', ', '.join(files) or '—')


def main(a):
    cmd = a.pop(0) if a else 'help'
    if cmd == 'sources':
        for s in call('sources?pageSize=100').get('sources', []):
            print(s['id'])
    elif cmd == 'new':
        branch, title = arg(a, '--branch', 'main'), arg(a, '--title')
        no_pr, plan = flag(a, '--no-pr'), flag(a, '--plan')
        repo, tz = a
        prompt = open(tz, encoding='utf-8').read()
        body = {'prompt': prompt, 'title': title or prompt.strip().splitlines()[0].lstrip('# ')[:100],
                'sourceContext': {'source': f'sources/github/{repo}', 'githubRepoContext': {'startingBranch': branch}},
                'requirePlanApproval': plan}
        if not no_pr:
            body['automationMode'] = 'AUTO_CREATE_PR'
        s = call('sessions', body)
        print('задача:', s['id'], '—', s.get('title'))
    elif cmd == 'status':
        s = call(sid(a[0]))
        print(s.get('state'), s.get('updateTime')); outputs(s)
    elif cmd == 'wait':
        end = time.time() + 60 * float(arg(a, '--minutes', '70'))
        while time.time() < end:
            s = call(sid(a[0]))
            if s.get('state') in DONE:
                print(s['state'], s.get('updateTime')); outputs(s)
                return 1 if s['state'] == 'FAILED' else 0
            time.sleep(60)
        print('не дождался:', s.get('state')); return 2
    elif cmd == 'log':
        every, acts, tok = flag(a, '--all'), [], ''
        while True:   # pageSize больше 30 API молча отдаёт пустым — только 30 и pageToken
            d = call(f'{sid(a[0])}/activities?pageSize=30' + (f'&pageToken={tok}' if tok else ''))
            acts += d.get('activities', []); tok = d.get('nextPageToken')
            if not tok:   # страницы идут от старых к новым — для последних 30 нужно пройти все
                break
        for x in acts[-30:] if not every else acts:
            p = x.get('progressUpdated') or {}
            text = p.get('title') or next((k for k in x if k not in ('name', 'id', 'createTime', 'originator', 'artifacts')), '')
            print(x.get('createTime', '')[11:19], x.get('originator', ''), text)
    elif cmd == 'patch':
        s = call(sid(a[0]))
        p = next((o['changeSet']['gitPatch']['unidiffPatch'] for o in s.get('outputs', []) if 'changeSet' in o), '')
        if not p:
            print('диффа нет'); return 1
        open(a[1], 'w', encoding='utf-8').write(p)
        print('сохранён:', a[1]); outputs(s)
    elif cmd == 'say':
        call(f'{sid(a[0])}:sendMessage', {'prompt': open(a[1], encoding='utf-8').read()})
        print('отправлено; ответ Jules — в журнале (log)')
    elif cmd == 'approve':
        call(f'{sid(a[0])}:approvePlan', {}); print('план одобрен')
    else:
        print(__doc__)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv[1:]))
