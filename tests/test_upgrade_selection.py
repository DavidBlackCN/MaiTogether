"""Release dates and adapter releases need not align with Host stable releases."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import upgrade


def manifest(host='1.3.18', sdk='2.0.0'):
    return {'host_application': {'min_version': host, 'max_version': '1.99.99'},
            'sdk': {'min_version': sdk, 'max_version': '2.99.99'}}


@pytest.mark.parametrize('host,sdk,expected', [
    ('v1.4.3', 'v2.22.1', 'v1.1.13'), ('v1.4.4', 'v2.22.1', 'v1.3.1'),
    ('v1.4.3', 'v2.21.0', 'v1.1.12')])
def test_latest_compatible_stable_adapter(monkeypatch, host, sdk, expected):
    pins = {k: {'repository': 'https://github.com/test/' + k} for k in ('host', 'sdk', 'adapter')}
    monkeypatch.setattr(upgrade, 'latest', lambda p: {'tag_name': host if p is pins['host'] else sdk})
    releases = [{'tag_name': tag, 'draft': draft, 'prerelease': pre} for tag, draft, pre in
                [('v1.1.12', False, False), ('v1.1.13', False, False),
                 ('v1.3.1', False, False), ('v9.0.0', True, False), ('v8.0.0', False, True)]]
    def fetch(url):
        if '/releases?' in url: return releases
        if '/v1.3.1/' in url: return manifest(host='1.4.4')
        if '/v1.1.13/' in url: return manifest(sdk='2.22.1')
        if '/v1.1.12/' in url: return manifest()
        raise AssertionError(url)
    monkeypatch.setattr(upgrade, 'read_json', fetch)
    selected, skipped = upgrade.select_releases(pins)
    assert selected['adapter']['tag_name'] == expected
    assert all(r['tag'] != expected for r in skipped)


def test_invalid_or_missing_bounds_are_not_assumed_compatible():
    with pytest.raises(KeyError): upgrade.adapter_compatible({}, 'v1.4.3', 'v2.22.1')
    broken = manifest(); broken['sdk']['min_version'] = 'unknown'
    with pytest.raises(ValueError): upgrade.adapter_compatible(broken, 'v1.4.3', 'v2.22.1')


def test_no_compatible_release_stops_upgrade(monkeypatch):
    pins = {k: {'repository': 'https://github.com/test/' + k} for k in ('host', 'sdk', 'adapter')}
    monkeypatch.setattr(upgrade, 'latest', lambda p: {'tag_name': 'v1.4.3' if p is pins['host'] else 'v2.22.1'})
    monkeypatch.setattr(upgrade, 'read_json', lambda url:
        [{'tag_name': 'v1.3.1', 'draft': False, 'prerelease': False}]
        if '/releases?' in url else manifest(host='1.4.4'))
    with pytest.raises(ValueError, match='No released adapter'):
        upgrade.select_releases(pins)


def test_explicit_adapter_still_requires_a_published_stable_release(monkeypatch):
    pins = {k: {'repository': 'https://github.com/test/' + k} for k in ('host', 'sdk', 'adapter')}
    monkeypatch.setattr(upgrade, 'latest', lambda p: {'tag_name': 'v1.4.3' if p is pins['host'] else 'v2.22.1'})
    monkeypatch.setattr(upgrade, 'read_json', lambda url: [
        {'tag_name': 'v1.1.13', 'draft': False, 'prerelease': False},
        {'tag_name': 'v9.0.0', 'draft': False, 'prerelease': True}])
    assert upgrade.select_releases(pins, 'v1.1.13')[0]['adapter']['tag_name'] == 'v1.1.13'
    with pytest.raises(ValueError, match='not an official stable release'):
        upgrade.select_releases(pins, 'v9.0.0')
