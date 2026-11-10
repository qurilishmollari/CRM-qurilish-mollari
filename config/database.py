from urllib.parse import parse_qs, unquote, urlsplit


def postgres_database(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or not parsed.path.strip('/'):
        raise ValueError('DATABASE_URL must be a valid PostgreSQL connection URL')
    options = {}
    query = parse_qs(parsed.query)
    if 'sslmode' in query:
        options['sslmode'] = query['sslmode'][-1]
    return {'ENGINE': 'django.db.backends.postgresql', 'NAME': unquote(parsed.path.lstrip('/')), 'USER': unquote(parsed.username or ''), 'PASSWORD': unquote(parsed.password or ''), 'HOST': parsed.hostname, 'PORT': parsed.port or 5432, 'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True, 'OPTIONS': options}
