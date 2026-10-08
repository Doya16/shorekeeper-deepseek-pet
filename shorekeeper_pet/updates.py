"""Read public release metadata. Never downloads or replaces application files."""
from dataclasses import dataclass
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .paths import VERSION, UPDATE_REPOSITORY

MAX_RESPONSE = 1_000_000


@dataclass(frozen=True)
class UpdateResult:
    status: str
    version: str = ''
    url: str = ''
    notes: str = ''
    message: str = ''


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d{1,5}\.\d{1,5}\.\d{1,5}', value):
        raise ValueError('Not a stable release version')
    return tuple(map(int, value.removeprefix('v').split('.')))


def releases_url(repository=UPDATE_REPOSITORY):
    return 'https://github.com/' + repository + '/releases/latest'


def parse_release(data, current=VERSION, repository=UPDATE_REPOSITORY):
    if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
        raise ValueError('Not a published stable release')
    tag = data.get('tag_name')
    version = version_tuple(tag)
    # Construct the destination from the configured repository, never from remote HTML.
    url = 'https://github.com/' + repository + '/releases/tag/' + urllib.parse.quote(tag, safe='')
    notes = data.get('body') or ''
    if not isinstance(notes, str):
        raise ValueError('Invalid release notes')
    return UpdateResult('available' if version > version_tuple(current) else 'current',
                        tag.removeprefix('v'), url, notes[:12000])


def check_latest(current=VERSION, repository=UPDATE_REPOSITORY, opener=None):
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(
        'https://api.github.com/repos/' + repository + '/releases/latest',
        headers={'Accept': 'application/vnd.github+json',
                 'User-Agent': 'Shorekeeper-Update-Check/' + current,
                 'X-GitHub-Api-Version': '2022-11-28'})
    try:
        with opener(request, timeout=8) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Release response too large')
        return parse_release(json.loads(raw.decode('utf8')), current, repository)
    except urllib.error.HTTPError as error:
        message = ('GitHub 暂时限制了请求，请稍后重试。' if error.code in (403, 429)
                   else '暂时没有可用的正式版本。' if error.code == 404
                   else '暂时无法连接 GitHub，请稍后重试。')
    except (OSError, ValueError, TypeError):
        message = '本次未能检查更新。请检查网络，或稍后再试。'
    return UpdateResult('unavailable', url=releases_url(repository), message=message)
