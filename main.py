"""Lee Moodle y avisa por WhatsApp de los exámenes (y tareas) de los grupos SMX A/B.

Modo prueba (por defecto): solo muestra qué mensajes se enviarían.
Modo envío: ``python main.py --send`` publica en los grupos mediante el puente
QR de ``bridge/`` (o un webhook HTTPS si se configura ``whatsapp.mode = webhook``).
"""
import argparse
import hashlib
import json
import logging
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / 'bridge' / 'bridge.cjs'

GROUP = re.compile(r'\bgrup(?:o)?\s*[-:]?\s*([AB])\b', re.I)
EXAM = re.compile(r'\b(?:examen|exàmens?|exámenes|prova|proves|prueba|quiz|qüestionari|cuestionario|control|test)\b', re.I)
MONTHS = {
    **dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13))),
    **dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13))),
    'setiembre': 9,
}
# dd/mm/yyyy  |  12 de maig de 2026  |  12 d'abril 2026  |  12 maig 2026 (formato Moodle)
# seguido opcionalmente de la hora: ", 23:59", " a les 10:00", " a las 10.30"
DATE = re.compile(
    r"(?:(\d{1,2})/(\d{1,2})/(\d{4})"
    r"|(\d{1,2})\s+(?:de\s+|d[’']\s*)?([a-zçàèéíòóúü]+)(?:,?\s+(?:de\s+)?(\d{4}))?)"
    r"(?:\s*[,—-]?\s*(?:a\s+l[ae]s?\s+|de\s+)?(\d{1,2})[:.](\d{2}))?",
    re.I,
)


def dates(text, tz, year):
    """Devuelve (fecha, tiene_hora, año_inferido) para cada fecha reconocida."""
    for match in DATE.finditer(text):
        d, m, y, cd, cm, cy, hh, mm = match.groups()
        if cd and cm.lower() not in MONTHS:
            continue
        try:
            value = datetime(int(y or cy or year), int(m) if m else MONTHS[cm.lower()], int(d or cd),
                             int(hh or 0), int(mm or 0), tzinfo=tz)
        except ValueError:
            continue
        yield value, hh is not None, not bool(y or cy)


def groups(text):
    return set(GROUP.findall(text.upper()))


def extract(html, course_url, fallback, tz, year):
    """Extrae actividades con fecha de la página de un curso.

    Cada resultado es un dict con title, group, due (ISO), timed, url y kind
    ("exam" o "task"). Lo ambiguo se descarta con un aviso en el log.
    """
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('script, style, nav'):
        node.decompose()
    result = []

    def add(title, text, url, context, kind):
        found = list(dates(text, tz, year))
        explicit = groups(context)
        if len(explicit) > 1:
            log.warning('Revisión necesaria: el texto menciona varios grupos: %s', title)
            return
        targets = explicit or set(fallback)
        if len(found) != 1 or not targets:
            log.warning('Revisión necesaria: fecha/grupo ambiguo: %s', title)
            return
        due, timed, inferred = found[0]
        if inferred:
            log.warning('Año inferido (%s), no se notifica automáticamente: %s', year, title)
            return
        for group in sorted(targets):
            result.append(dict(title=title, group=group, due=due.isoformat(), timed=timed, url=url, kind=kind))

    for activity in soup.select('li.activity, .activity-item'):
        if activity.find_parent('li', class_='activity') and activity.name != 'li':
            continue
        text = activity.get_text(' ', strip=True)
        marker = re.search(r'\b(?:Venciment|Tancament|Fecha de entrega|Cierre|Due|Closes)\s*:', text, re.I)
        if not marker:
            continue
        link = activity.select_one('.activityname a, a[href*="/mod/assign/"], a[href*="/mod/quiz/"], .instancename')
        name = activity.select_one('.instancename') or link
        title = name.get_text(' ', strip=True) if name else text[:160]
        href = link.get('href', '') if link and link.name == 'a' else ''
        url = urljoin(course_url, href) if href else course_url
        kind = 'exam' if '/mod/quiz/' in url or EXAM.search(title) else 'task'
        add(title, text[marker.end():], url, text, kind)

    for block in soup.select('.summary, .contentwithoutlink, .description .no-overflow'):
        lines = [s.strip() for s in block.get_text('\n', strip=True).splitlines() if s.strip()]
        title = None
        for line in lines:
            if EXAM.search(line):
                title = line
            if title and GROUP.search(line) and DATE.search(line):
                add(title, line, course_url, line, 'exam')
    return result


def eligible(event, now):
    due = datetime.fromisoformat(event['due'])
    if event['timed']:
        return now <= due <= now + timedelta(hours=48)
    return 0 <= (due.date() - now.date()).days <= 2


def build_message(event):
    due = datetime.fromisoformat(event['due'])
    when = due.strftime('%d/%m/%Y %H:%M') if event['timed'] else due.strftime('%d/%m/%Y') + ' (hora no indicada)'
    label = '📝 EXAMEN' if event['kind'] == 'exam' else '📌 Entrega'
    return f"{label} — SMX ({event['group']})\n{event['title']}\n🗓️ {when}\n{event['url']}"


def event_key(event):
    return hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()


class Uncertain(RuntimeError):
    """El mensaje pudo haberse enviado, pero no hay confirmación."""


def send_bridge(cfg_path, group, text, timeout=300):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('No se encuentra Node.js: instálalo para usar el puente QR')
    if not (BRIDGE.parent / 'node_modules').exists():
        raise RuntimeError('Faltan dependencias del puente: ejecuta "cd bridge && npm install"')
    try:
        proc = subprocess.run([node, str(BRIDGE), 'send', str(cfg_path)],
                              input=json.dumps({'group': group, 'text': text}),
                              capture_output=True, text=True, timeout=timeout, cwd=BRIDGE.parent)
    except subprocess.TimeoutExpired as error:
        raise Uncertain('El puente no respondió a tiempo') from error
    for line in proc.stderr.strip().splitlines():
        log.info('puente: %s', line)
    if proc.returncode == 3:
        raise Uncertain('WhatsApp no confirmó la recepción del mensaje')
    if proc.returncode != 0:
        raise RuntimeError(f'El puente falló (código {proc.returncode})')
    lines = proc.stdout.strip().splitlines()
    if not lines or json.loads(lines[-1]).get('sent') is not True:
        raise Uncertain('El puente no confirmó el envío')


def send_webhook(hook, group, text, key):
    target = hook['groups'][group]
    if not target or not hook.get('webhook_url', '').startswith('https://'):
        raise ValueError('Configura un webhook HTTPS y el ID del grupo')
    try:
        response = requests.post(hook['webhook_url'], headers={'Authorization': 'Bearer ' + hook['token']},
                                 json={'group_id': target, 'text': text, 'idempotency_key': key}, timeout=30)
    except requests.Timeout as error:
        raise Uncertain('Timeout del webhook') from error
    response.raise_for_status()
    if response.json().get('sent') is not True:
        raise RuntimeError('El puente no confirmó el envío; no se marca como entregado')


def moodle_session(cfg):
    base = cfg['moodle']['base_url'].rstrip('/') + '/'
    parsed = urlparse(base)
    session = requests.Session()
    for item in cfg['moodle']['cookie'].split(';'):
        name, sep, value = item.strip().partition('=')
        if sep:
            session.cookies.set(name, value, domain=parsed.hostname, path=parsed.path)
    session.headers['User-Agent'] = 'cmps-script/2.1'

    def page(url):
        target = urlparse(url)
        if target.netloc != parsed.netloc or not target.path.startswith(parsed.path):
            raise ValueError('URL fuera del Moodle configurado')
        response = session.get(url, timeout=30, allow_redirects=False)
        response.raise_for_status()
        if response.is_redirect or 'login/index.php' in response.url or re.search(r'name=["\x27]logintoken', response.text):
            raise RuntimeError('Sesión no válida o redirección: renueva la cookie de Moodle')
        return response.text

    return base, session, page


def main(argv=None):
    parser = argparse.ArgumentParser(description='Avisos de exámenes de Moodle por WhatsApp')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--send', action='store_true', help='Enviar de verdad (sin esto solo es una prueba)')
    args = parser.parse_args(argv)
    cfg_path = Path(args.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    tz = ZoneInfo(cfg.get('timezone', 'Europe/Madrid'))
    now = datetime.now(tz)
    only_exams = cfg.get('only_exams', False)
    hook = cfg['whatsapp']
    mode = hook.get('mode') or ('webhook' if hook.get('webhook_url') else 'bridge')
    if mode not in ('bridge', 'webhook'):
        raise ValueError('whatsapp.mode debe ser "bridge" o "webhook"')

    base, session, page = moodle_session(cfg)
    courses = set(cfg['moodle'].get('course_urls', []))
    for a in BeautifulSoup(page(urljoin(base, 'my/courses.php')), 'html.parser').select('a[href]'):
        url = urljoin(base, a['href'])
        if '/course/view.php?' in url:
            courses.add(url)
    if not courses:
        raise RuntimeError('No se descubrieron cursos; configura course_urls con sus URLs autorizadas')

    dbpath = Path(cfg.get('database_path', 'data/groups.sqlite3'))
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(dbpath)
    db.execute('CREATE TABLE IF NOT EXISTS deliveries (key TEXT PRIMARY KEY)')
    sent = pending = 0
    try:
        for course in sorted(courses):
            fallback = cfg.get('course_groups', {}).get(course, [])
            if not set(fallback) <= {'A', 'B'}:
                raise ValueError('Solo se admiten grupos A/B')
            for event in extract(page(course), course, fallback, tz, now.year):
                if only_exams and event['kind'] != 'exam':
                    continue
                if not eligible(event, now):
                    continue
                key = event_key(event)
                if db.execute('SELECT 1 FROM deliveries WHERE key=?', (key,)).fetchone():
                    continue
                text = build_message(event)
                if not args.send:
                    pending += 1
                    log.info('[PRUEBA] Se enviaría al grupo %s:\n%s', event['group'], text)
                    continue
                try:
                    if mode == 'bridge':
                        send_bridge(cfg_path, event['group'], text)
                    else:
                        send_webhook(hook, event['group'], text, key)
                except Uncertain as error:
                    # Se marca igualmente para no repetir: un duplicado molesta más que revisar a mano.
                    log.error('%s. Revisa el grupo %s: "%s"', error, event['group'], event['title'])
                db.execute('INSERT OR IGNORE INTO deliveries VALUES (?)', (key,))
                db.commit()
                sent += 1
                log.info('Enviado al grupo %s: %s', event['group'], event['title'])
    finally:
        db.close()
        session.close()
    if args.send:
        log.info('Fin: %d aviso(s) enviado(s).', sent)
    else:
        log.info('Fin (modo prueba): %d aviso(s) pendiente(s). Usa --send para enviarlos.', pending)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
