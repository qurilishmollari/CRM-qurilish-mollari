from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def trusted_origins(value, railway_domain=''):
    values = value.split(',')
    if railway_domain:
        values.append(railway_domain)
    result = []
    for entry in values:
        entry = entry.strip()
        if not entry:
            continue
        if '://' not in entry:
            entry = 'https:' + entry if entry.startswith('//') else 'https://' + entry
        try:
            parsed = urlsplit(entry)
            parsed.port  # Validate optional port syntax.
            valid = (parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not parsed.password and parsed.path in ('', '/') and not parsed.query and not parsed.fragment and not any(char.isspace() for char in parsed.netloc) and parsed.hostname != '*')
        except ValueError:
            valid = False
        if not valid:
            raise ImproperlyConfigured('DJANGO_CSRF_TRUSTED_ORIGINS must contain domains or http(s) origins without paths, credentials or query parameters.')
        origin = f'{parsed.scheme}://{parsed.netloc.lower()}'
        if origin not in result:
            result.append(origin)
    return result
