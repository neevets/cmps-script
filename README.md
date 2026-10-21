# CMPS Script — Avisos de Moodle a WhatsApp

Bot en Python que revisa las tareas, cuestionarios y exámenes de Moodle con entrega en las próximas 48 horas y envía avisos por WhatsApp mediante CallMeBot.

## Características

- Lee todos los cursos del usuario.
- Detecta tareas, cuestionarios/exámenes y eventos de entrega.
- Avisa cuando faltan 48 horas o menos.
- Evita avisos duplicados con SQLite.
- Configuración mediante `config.json`.
- Dos modos de acceso a Moodle: token de Web Services o cookie de sesión.
- Enrutado por curso: `announce`, `group_a`, `group_b` o `all`.

## Importante: grupos de WhatsApp

CallMeBot envía mensajes individuales, no a grupos. Este bot envía el mismo aviso a cada número configurado en la lista correspondiente.

## Instalación

```bash
git clone https://github.com/neevets/cmps-script.git
cd cmps-script
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Edita `config.json` con tu cookie o token, los números de WhatsApp y el enrutado de cursos.

## Ejecución manual

```bash
python main.py
```

## Cron en VPS

Cada 12 horas, a las 08:00 y 20:00:

```cron
0 8,20 * * * cd /opt/cmps-script && /opt/cmps-script/.venv/bin/python main.py >> /var/log/cmps-script.log 2>&1
```

## Seguridad

- No subas `config.json`, cookies ni tokens a GitHub.
- Usa `config.example.json` como plantilla.
- El bot debe usarse únicamente con tu propia cuenta de Moodle.
