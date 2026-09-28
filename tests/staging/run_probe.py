"""Run synthetic, non-filing regression interviews on apps-dev.

Requires requests, PyYAML, BeautifulSoup, and the apps-dev ~/.docassemblecli entry.
Deploy both fixes first. Uploads dedicated Playground files; does not change config.
"""
from pathlib import Path
import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
CONFIG = next(c for c in yaml.safe_load(Path.home().joinpath('.docassemblecli').read_text())
              if c['name'] == 'apps-dev.suffolklitlab.org')
BASE = CONFIG['apiurl'].rstrip('/')
API = requests.Session()
API.headers['X-API-Key'] = CONFIG['apikey']


def call(method, path, **kwargs):
    result = API.request(method, BASE + path, timeout=60, **kwargs)
    if not result.ok:
        raise RuntimeError(f'{path}: {result.status_code}: {result.text[:500]}')
    return result


def upload(name, content, folder='questions'):
    call('POST', '/api/playground', data={'folder': folder, 'restart': False},
         files={'file': (name, content)})


def question(session):
    return call('GET', '/api/session/question', params=session).json()


def set_vars(session, variables):
    call('POST', '/api/session', json={**session, 'variables': variables, 'question': False})


def probe_blocks(uid, indexed=False):
    source = ROOT / 'docassemble/MAPetitionToSealEviction/data/questions/support_efiling.yml'
    blocks = [b for b in yaml.safe_load_all(source.read_text()) if isinstance(b, dict)]
    ids = {'resolve selected case labels', 'resolve search result labels',
           'determine efiling availability', 'retry efiling metadata',
           'predict eviction reason from verified metadata', 'warn_sorry_not_efileable'}
    result = [b for b in blocks if b.get('initial')]
    result += [dict(modules=['docassemble.EFSPIntegration.interview_logic',
                            'docassemble.MAPetitionToSealEviction.efiling_metadata',
                            f'docassemble.playground{uid}.issue305_fixtures']),
               dict(objects=[{'case_search': 'EFCaseSearch'}, {'trial_court': 'DAObject'}])]
    setup = '''can_check_efile = True
trial_court.department = "Housing Court"
proxy_conn = MetadataProxy()
case_search.found_case = DAObject('case_search.found_case')
case_search.found_case.court_id = 'child'
case_search.found_case.case_type = '8731'
case_search.found_case.category = '8730'
setup_done = True'''
    order = 'setup_done\nif not petition_is_efileable:\n  warn_sorry_not_efileable\nprobe_done'
    if indexed:
        setup = '''can_check_efile = True
trial_court.department = "Housing Court"
proxy_conn = MetadataProxy('valid')
case_search.found_cases = DAList('case_search.found_cases', object_type=DAObject, gathered=True)
for probe_index in range(2):
  probe_case = case_search.found_cases.appendObject()
  probe_case.court_id = 'child-' + str(probe_index)
  probe_case.case_type = '8731'
  probe_case.category = '8730'
setup_done = True'''
        order = '''setup_done
assert case_search.found_cases[0].case_type_name == 'No Cause'
assert case_search.found_cases[1].case_category_name == 'Summary Process'
case_search.found_case = case_search.found_cases[1]
assert petition_is_efileable
probe_done'''
    result += [{'only sets': ['setup_done'], 'code': setup},
               {'mandatory': True, 'code': order},
               {'event': 'probe_done', 'question': 'Probe complete', 'subquestion': '''Eligible: ${ petition_is_efileable }
Type: ${ case_search.found_case.case_type_name }
Category: ${ case_search.found_case.case_category_name }
Prediction: ${ predicted_eviction_reason }
Can check efile: ${ can_check_efile }
Calls: ${ proxy_conn.calls }'''}]
    result += [b for b in blocks if b.get('id') in ids]
    return result


def browser_manual(interview):
    # The variables API does not execute question validation code. Use a browser form.
    browser = requests.Session()
    response = browser.get(BASE + '/interview', params={'i': interview, 'new_session': 1}, timeout=60)
    soup = BeautifulSoup(response.text, 'html.parser')
    assert 'E-filing is temporarily unavailable' in soup.get_text()
    form = soup.find('form', id='daform')
    data = {i['name']: i.get('value', '') for i in form.find_all('input')
            if i.get('name') and i.get('type') == 'hidden'}
    for button in form.find_all('button'):
        if button.get('type') == 'submit' and button.get('name'):
            data[button['name']] = button.get('value', '')
            break
    response = browser.post(requests.compat.urljoin(response.url, form.get('action', '')),
                            data=data, headers={'Referer': response.url}, timeout=60)
    text = BeautifulSoup(response.text, 'html.parser').get_text(' ', strip=True)
    assert 'Can check efile: False' in text, text[-1000:]
    assert 'Eligible: False' in text


def main():
    uid = call('GET', '/api/user').json()['id']
    fixture = Path(__file__).with_name('issue305_fixtures.py')
    upload(fixture.name, fixture.read_text(), 'modules')
    for indexed in (False, True):
        name = 'issue305_indexed_probe.yml' if indexed else 'issue305_probe.yml'
        upload(name, yaml.safe_dump_all(probe_blocks(uid, indexed), sort_keys=False))
        interview = f'docassemble.playground{uid}:{name}'
        session = call('GET', '/api/session/new', params={'i': interview}).json()
        try:
            q = question(session)
            if indexed:
                assert q['questionText'] == 'Probe complete', q
                assert 'child-1' in q['subquestionText']
                print('PASS: indexed results and selection')
                continue
            assert q['questionText'] == 'E-filing is temporarily unavailable', q
            set_vars(session, {'proxy_conn.mode': 'valid'})
            call('POST', '/api/session/action', json={**session, 'action': 'retry_efiling_metadata'})
            q = question(session)
            assert 'Eligible: True' in q['subquestionText'], q
            assert 'eviction_reason_nofault' in q['subquestionText']
            set_vars(session, {'case_search.found_case.court_id': 'second-child'})
            assert 'second-child' in question(session)['subquestionText']
            set_vars(session, {'proxy_conn.mode': 'null'})
            assert question(session)['questionText'] == 'E-filing is temporarily unavailable'
            print('PASS: null response, retry recovery, changed court, stale-label invalidation')
            browser_manual(interview)
            print('PASS: browser Continue disables e-filing')
        finally:
            call('DELETE', '/api/session', params={'i': interview, 'session': session['session']})


if __name__ == '__main__':
    main()
