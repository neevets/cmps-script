import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: E402

TZ = ZoneInfo('Europe/Madrid')
COURSE = 'https://moodle.test/course/view.php?id=7'

HTML = """
<ul>
 <li class="activity quiz">
  <div class="activityname"><a href="/mod/quiz/view.php?id=1"><span class="instancename">Examen UF2 Grup A</span></a></div>
  <div>Tancament: dimarts, 12 maig 2026, 10:00</div>
 </li>
 <li class="activity assign">
  <div class="activityname"><a href="/mod/assign/view.php?id=2"><span class="instancename">Pràctica 3</span></a></div>
  <div>Venciment: 13 de maig de 2026, 23:59</div>
 </li>
</ul>
<div class="summary"><p>Prova de xarxes</p><p>Grup B: 14 d'abril de 2026 a les 9:30</p></div>
"""


def test_dates_formats():
    cases = {
        '12/05/2026': (datetime(2026, 5, 12, tzinfo=TZ), False),
        '12 de maig de 2026, 23:59': (datetime(2026, 5, 12, 23, 59, tzinfo=TZ), True),
        "3 d'octubre 2026 a les 8.15": (datetime(2026, 10, 3, 8, 15, tzinfo=TZ), True),
        'dimarts, 12 maig 2026, 10:00': (datetime(2026, 5, 12, 10, 0, tzinfo=TZ), True),
        '5 de junio de 2026': (datetime(2026, 6, 5, tzinfo=TZ), False),
    }
    for text, (expected, timed) in cases.items():
        found = list(main.dates(text, TZ, 2026))
        assert [(f[0], f[1], f[2]) for f in found] == [(expected, timed, False)], text


def test_year_missing_is_flagged():
    (_, _, inferred), = main.dates('12 de maig', TZ, 2026)
    assert inferred


def test_extract_kinds_and_groups():
    events = main.extract(HTML, COURSE, ['A'], TZ, 2026)
    by_title = {e['title']: e for e in events}
    exam = by_title['Examen UF2 Grup A']
    assert exam['kind'] == 'exam' and exam['group'] == 'A' and exam['timed']
    assert exam['url'] == 'https://moodle.test/mod/quiz/view.php?id=1'
    assert by_title['Pràctica 3']['kind'] == 'task'
    announcement = by_title['Prova de xarxes']
    assert announcement['group'] == 'B' and announcement['due'].startswith('2026-04-14T09:30')


def test_shared_course_goes_to_both_groups():
    html = '<li class="activity"><a href="/mod/quiz/view.php?id=9"><span class="instancename">Test xarxes</span></a> Tancament: 12/05/2026</li>'
    events = main.extract(html, COURSE, ['A', 'B'], TZ, 2026)
    assert sorted(e['group'] for e in events) == ['A', 'B']


def test_two_groups_in_text_is_ambiguous():
    html = '<li class="activity"><a href="/mod/quiz/view.php?id=9"><span class="instancename">Examen grup A i grup B</span></a> Tancament: 12/05/2026</li>'
    assert main.extract(html, COURSE, [], TZ, 2026) == []


def test_eligible_window():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=TZ)
    ev = dict(due=datetime(2026, 5, 12, 10, 0, tzinfo=TZ).isoformat(), timed=True)
    assert main.eligible(ev, now)
    ev['due'] = datetime(2026, 5, 14, 10, 0, tzinfo=TZ).isoformat()
    assert not main.eligible(ev, now)
    assert main.eligible(dict(due=datetime(2026, 5, 13, tzinfo=TZ).isoformat(), timed=False), now)


def test_message_text():
    ev = dict(title='Examen UF2', group='A', due='2026-05-12T10:00:00+02:00', timed=True, url='u', kind='exam')
    assert main.build_message(ev) == '📝 EXAMEN — SMX (A)\nExamen UF2\n🗓️ 12/05/2026 10:00\nu'


def test_send_bridge_ok_and_failures(tmp_path):
    ok = subprocess.CompletedProcess([], 0, stdout='{"sent": true, "message_id": "x"}\n', stderr='')
    with mock.patch.object(main.shutil, 'which', return_value='/usr/bin/node'), \
         mock.patch.object(main.Path, 'exists', return_value=True), \
         mock.patch.object(main.subprocess, 'run', return_value=ok) as run:
        main.send_bridge(tmp_path / 'c.json', 'B', 'hola')
        assert json.loads(run.call_args.kwargs['input']) == {'group': 'B', 'text': 'hola'}
        run.return_value = subprocess.CompletedProcess([], 3, stdout='', stderr='')
        with pytest.raises(main.Uncertain):
            main.send_bridge(tmp_path / 'c.json', 'B', 'hola')
        run.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='Sesión caducada')
        with pytest.raises(RuntimeError):
            main.send_bridge(tmp_path / 'c.json', 'B', 'hola')
