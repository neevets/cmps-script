import argparse
import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
GROUP = re.compile(r'\bgrup(?:o)?\s*[-:]?\s*([AB])\b', re.I)
MONTHS = dict(zip(('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre').split(), range(1, 13)))
DATE = re.compile(r"(?:(\d{1,2})/(\d{1,2})/(\d{4})|(\d{1,2})\s+d[’']([a-zç]+)(?:\s+(?:de\s+)?(\d{4}))?)(?:\s*[,—-]?\s*(?:de\s+)?(\d{1,2})[:.](\d{2}))?", re.I)


def dates(text, tz, year):
    for match in DATE.finditer(text):
        d, m, y, cd, cm, cy, hh, mm = match.groups()
        if cd and cm.lower() not in MONTHS:
            continue
        try:
            value = datetime(int(y or cy or year), int(m) if m else MONTHS[cm.lower()], int(d or cd), int(hh or 0), int(mm or 0), tzinfo=tz)
        except ValueError:
            continue
        yield value, hh is not None, not bool(y or cy)


def groups(text):
    return set(GROUP.findall(text.upper()))


def extract(html, course_url, fallback, tz, year):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script, style, nav'):
        node.decompose()
    result = []
    def add(title, text, url, context, due_only=False):
        found = list(dates(text, tz, year))
        targets = groups(context) or set(fallback)
        if len(found) != 1 or len(targets) != 1:
            log.warning('Revisión necesaria: fecha/grupo ambiguo: %s', title)
            return
        due, timed, inferred = found[0]
        if inferred:
            log.warning('Año inferido (%s), no se notifica automáticamente: %s', year, title)
            return
        result.append(dict(title=title, group=next(iter(targets)), due=due.isoformat(), timed=timed, url=url))
    for activity in soup.select('li.activity, .activity-item'):
        if activity.find_parent('li', class_='activity') and activity.name != 'li':
            continue
        text = activity.get_text(' ', strip=True)
        marker = re.search(r'\b(?:Venciment|Fecha de entrega|Due)\s*:', text, re.I)
        if not marker:
            continue
        link = activity.select_one('.activityname a, .instancename, a[href*="/mod/assign/"], a[href*="/mod/quiz/"]')
        title = link.get_text(' ', strip=True) if link else text[:160]
        href = link.get('href', '') if link else ''
        add(title, text[marker.end():], urljoin(course_url, href) if href else course_url, text)
    for block in soup.select('.summary, .contentwithoutlink, .description .no-overflow'):
        lines = [s.strip() for s in block.get_text('\n', strip=True).splitlines() if s.strip()]
        title = None
        for line in lines:
            if re.search(r'\b(?:examen|prova|quiz|cuestionario)\b', line, re.I):
                title = line
            if title and GROUP.search(line) and DATE.search(line):
                add(title, line, course_url, line)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--send', action='store_true', help='Enviar mediante el webhook configurado')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    tz = ZoneInfo(cfg.get('timezone', 'Europe/Madrid'))
    now = datetime.now(tz)
    base = cfg['moodle']['base_url'].rstrip('/') + '/'
    origin = urlparse(base).netloc
    session = requests.Session()
    cookie = cfg['moodle']['cookie']
    for item in cookie.split(';'):
        name, sep, value = item.strip().partition('=')
        if sep:
            session.cookies.set(name, value, domain=urlparse(base).hostname, path=urlparse(base).path)
    session.headers['User-Agent'] = 'cmps-script/2.0'
    def page(url):
        if urlparse(url).netloc != origin or not urlparse(url).path.startswith(urlparse(base).path):
            raise ValueError('URL fuera del Moodle configurado')
        response = session.get(url, timeout=30, allow_redirects=False)
        response.raise_for_status()
        if response.is_redirect or 'login/index.php' in response.url or re.search(r'name=[\"\x27]logintoken', response.text):
            raise RuntimeError('Sesión no válida o redirección: renueva la cookie')
        return response.text
    html = page(urljoin(base, 'my/courses.php'))
    courses = set(cfg['moodle'].get('course_urls', []))
    for a in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = urljoin(base, a['href'])
        if '/course/view.php?' in url:
            courses.add(url)
    if not courses:
        raise RuntimeError('No se descubrieron cursos; configura course_urls con sus URLs autorizadas')
    dbpath = Path(cfg.get('database_path', 'data/groups.sqlite3'))
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(dbpath)
    db.execute('CREATE TABLE IF NOT EXISTS deliveries (key TEXT PRIMARY KEY)')
    try:
        for course in sorted(courses):
            fallback = cfg.get('course_groups', {}).get(course, [])
            if not set(fallback) <= {'A', 'B'}:
                raise ValueError('Solo se admiten grupos A/B')
            events = extract(page(course), course, fallback, tz, now.year)
            for event in events:
                due = datetime.fromisoformat(event['due'])
                eligible = (now <= due <= now + timedelta(hours=48)) if event['timed'] else (0 <= (due.date() - now.date()).days <= 2)
                if not eligible:
                    continue
                key = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
                if db.execute('SELECT 1 FROM deliveries WHERE key=?', (key,)).fetchone():
                    continue
                log.info('Candidato: %s', json.dumps(event, ensure_ascii=False))
                if not args.send:
                    continue
                hook = cfg['whatsapp']
                target = hook['groups'][event['group']]
                if not target or not hook.get('webhook_url', '').startswith('https://'):
                    raise ValueError('Configura un webhook HTTPS y el ID del grupo')
                when = due.strftime('%d/%m/%Y %H:%M') if event['timed'] else due.strftime('%d/%m/%Y') + ' — hora no indicada'
                text = f"Moodle — SMX ({event['group']})\n{event['title']}\n{when}\n{event['url']}"
                response = requests.post(hook['webhook_url'], headers={'Authorization': 'Bearer ' + hook['token']}, json={'group_id': target, 'text': text, 'idempotency_key': key}, timeout=30)
                response.raise_for_status()
                if response.json().get('sent') is not True:
                    raise RuntimeError('El puente no confirmó el envío; no se marca como entregado')
                db.execute('INSERT OR IGNORE INTO deliveries VALUES (?)', (key,))
                db.commit()
    finally:
        db.close()
        session.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
