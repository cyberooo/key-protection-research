import requests
import json
import time
import os
import re

authorization = '[TYPE IN YOUR GITHUB TOKEN HERE]'

github_base_url = 'https://api.github.com'
gh_header = {
    'Accept': 'application/vnd.github+jso',
    'Authorization': 'Bearer ' + authorization,
    'X-GitHub-Api-Version': '2022-11-28'
}
rel_next_pattern = r'(?<=<)([\S]*)(?=>; rel="Next")'
query_cache = {}
query_count_cache = {}

class Log:
    @staticmethod
    def send(msg):
        print('[Send] ' + str(msg))
    
    @staticmethod
    def print(msg):
        print(msg)

    @staticmethod
    def info(msg):
        print('[Info] ' + str(msg))

    @staticmethod
    def warn(msg):
        print('\033[0;33m[Warning] ' + str(msg) + '\033[0m')

    @staticmethod
    def error(msg):
        print('\033[0;31m[Error] ' + str(msg) + '\033[0m')

def gh_search_code_count(query, retry = 5):
    if query in query_count_cache.keys():
        return query_count_cache[query]
    params = { 'q': query, 'per_page': 100 }
    max_retry = retry
    while retry >= 0:
        try:
            response = requests.get(github_base_url + '/search/code', params = params, headers = gh_header, timeout = 60)
            if response.status_code == 200:
                response_json = json.loads(response.text)
                total_count = response_json['total_count']
                query_count_cache[query] = total_count
                return total_count
            elif response.status_code == 403:
                if retry > 0:
                    wait_time = (max_retry - retry + 1) * 10
                    retry = retry - 1
                    time.sleep(wait_time)
                    continue
        except requests.exceptions.RequestException as e:
            if retry > 0:
                wait_time = (max_retry - retry + 1) * 5
                retry = retry - 1
                time.sleep(wait_time)
                continue
    return -1

def get_search_code_count_distribution(search_key):
    step = 10 ** 2
    step_count_total = 0
    # for i in range(0, 10 ** 4, step):
    #     step_count = gh_search_code_count(search_key + ' size:' + str(i) + '..' + str(i + step), retry=10)
    #     Log.info('Step result ' + str(i) + '..' + str(i + step) + ': ' + str(step_count))
    #     step_count_total = step_count_total + step_count
    step = 10 ** 4
    for i in range(10 ** 4, 10 ** 5, step):
        step_count = gh_search_code_count(search_key + ' size:' + str(i) + '..' + str(i + step), retry=10)
        Log.info('Step result ' + str(i) + '..' + str(i + step) + ': ' + str(step_count))
        step_count_total = step_count_total + step_count
    step = 10 ** 5
    for i in range(10 ** 5, 384 * 1000, step):
        step_count = gh_search_code_count(search_key + ' size:' + str(i) + '..' + str(i + step), retry=10)
        Log.info('Step result ' + str(i) + '..' + str(i + step) + ': ' + str(step_count))
        step_count_total = step_count_total + step_count
    Log.info('step_count_total: ' + str(step_count_total))

def gh_fetch_paginated_responses(header_link, parse_func, retry = 5):
    if header_link:
        next_link = re.search(rel_next_pattern, header_link, re.I)
        if next_link:
            next_link = next_link.group()
            max_retry = retry
            while retry >= 0:
                try:
                    response = requests.get(next_link, headers = gh_header, timeout = 60)
                    if response.status_code == 200:
                        Log.info(next_link)
                        return parse_func(response) + gh_fetch_paginated_responses(response.headers['Link'], parse_func, max_retry)
                    elif response.status_code == 403:
                        if retry > 0:
                            wait_time = (max_retry - retry + 1) * 10
                            retry = retry - 1
                            time.sleep(wait_time)
                            continue
                except requests.exceptions.RequestException as e:
                    if retry > 0:
                        wait_time = (max_retry - retry + 1) * 5
                        Log.warn('[Retry] Network request exception, retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                        retry = retry - 1
                        time.sleep(wait_time)
                        continue
            Log.error('Fetch paginated responses failed...')
    return []

def gh_search_code(query, retry = 5):
    if query in query_cache.keys():
        return query_cache[query]
    params = { 'q': query, 'per_page': 100 }
    max_retry = retry
    while retry >= 0:
        try:
            response = requests.get(github_base_url + '/search/code', params = params, headers = gh_header, timeout = (30, 120), allow_redirects = False)
            if response.status_code == 200:
                Log.info(response.request.url)
                first_page_response = parse_gh_search_code_response(response)
                if 'Link' in response.headers.keys():
                    all_pages_response = first_page_response + gh_fetch_paginated_responses(response.headers['Link'], parse_gh_search_code_response, max_retry)
                    query_cache[query] = all_pages_response
                    return all_pages_response
                else:
                    query_cache[query] = first_page_response
                    return first_page_response
            elif response.status_code == 403:
                if retry > 0:
                    wait_time = (max_retry - retry + 1) * 10
                    Log.warn('[Retry] GitHub API limitation due to http status ' + str(response.status_code) + ', retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                    retry = retry - 1
                    time.sleep(wait_time)
                    continue
        except requests.exceptions.RequestException as e:
            if retry > 0:
                wait_time = (max_retry - retry + 1) * 5
                Log.warn('[Retry] Network request exception, retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                retry = retry - 1
                time.sleep(wait_time)
                continue
        
    Log.error('Search code request failed...')
    return []

def parse_gh_search_code_response(response):
    response_json = json.loads(response.text)
    items = response_json['items']
    parse_result = []
    for item in items:
        name = item['name']
        path = item['path']
        html_url = item['html_url']
        repository_name = item['repository']['name']
        repository_full_name = item['repository']['full_name']
        repository_html_url = item['repository']['html_url']
        owner_login = item['repository']['owner']['login']
        owner_html_url = item['repository']['owner']['html_url']
        parse_result.append(
            {
                'name': name,
                'path': path,
                'html_url': html_url,
                'repository_name': repository_name,
                'repository_full_name': repository_full_name,
                'repository_html_url': repository_html_url,
                'owner_login': owner_login,
                'owner_html_url': owner_html_url
            }
        )
    return parse_result

def search_code_full(search_key, search_policy):
    full_result = []
    for per_search_policy in search_policy:
        start = per_search_policy[0]
        end = per_search_policy[1]
        step = per_search_policy[2]
        if step == -1:
            step = end - start
        for i in range(start, end, step):
            start_time = time.time()
            step_result = gh_search_code(search_key + ' size:' + str(i) + '..' + str(i + step), retry=10)
            end_time = time.time()
            Log.info('Step result ' + str(i) + '..' + str(i + step) + ' count: ' + str(len(step_result)) + ', speed: ' + str(len(step_result) / (end_time - start_time)) + ' results/sec')
            full_result = full_result + step_result

    result_len = len(full_result)
    Log.info('Get ' + str(result_len) + ' result from search.')
    return full_result

def dl_results(results, base_dir, is_override = True):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok = True)
    progress = 0
    total = len(results)
    for per_result in results:
        Log.info('[' + str(progress) + '/' + str(total) + ']')
        dl_single_result(per_result, base_dir, is_override)

def dl_single_result(result, base_dir, is_override = True):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok = True)
    fs_file_path = get_file_path(base_dir, result['repository_full_name'], result['path'])
    if os.path.exists(fs_file_path) and not is_override:
        return
    Log.info('Start download file to ' + fs_file_path)
    fs_file_dir, fs_file_name = os.path.split(fs_file_path)
    try:
        os.makedirs(fs_file_dir, exist_ok = True)
        dl_file(result['html_url'], fs_file_path)
    except BaseException as e:
        Log.error(e)

# Convent and download url: 
# https://github.com/{user}/{repository}/blob/{SHA-1}/{file} --> https://raw.githubusercontent.com/{user}/{repository}/{SHA-1}/{file}
def dl_file(html_url, target_file):
    dl_url = html_url.replace('github.com', 'raw.githubusercontent.com', 1).replace('blob/', '')
    Log.info('Start download file: ' + dl_url)
    response = requests.get(dl_url)
    if response.status_code == 200:
        with open(target_file, 'wb') as f:
            f.write(response.content)
    elif response.status_code == 403:
        Log.error('403 when dl_file')
    else:
        Log.error(response.status_code)

def write_result_to_file(result, file_name):
    with open(file_name, 'w') as f:
        f.write(json.dumps(result))

def parse_result_from_file(result_file):
    with open(result_file, 'r') as f:
        parse_results = f.read()
        parse_results = json.loads(parse_results)
        return parse_results

def get_file_path(base_dir, repo, path):
    fs_repository_path = os.path.abspath(os.path.join(base_dir, repo))
    fs_file_path = os.path.abspath(os.path.join(fs_repository_path, path))
    return fs_file_path

def read_file(base_dir, repo, path):
    fs_file_path = get_file_path(base_dir, repo, path)
    if not os.path.exists(fs_file_path):
        Log.error('Result file not exists: ' + fs_file_path)
        return ''
    if not os.path.isfile(fs_file_path):
        Log.error('Result file is a directory : ' + fs_file_path)
        return ''
    with open(fs_file_path, 'rb') as f:
        return f.read()

def dl_results_repos(results, base_dir):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok = True)
    progress = 0
    total = len(results)
    for per_result in results:
        Log.info('[' + str(progress) + '/' + str(total) + '] Start download repo ' + per_result['repository_html_url'])
        dl_result_repo(per_result)
        progress = progress + 1

def dl_result_repo(result, base_dir):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok = True)
    return dl_repo_zipball(result['owner_login'], result['repository_name'], base_dir, retry=10)

def dl_repo_zipball(owner_login, repository_name, base_dir, retry = 5):
    target_dir = os.path.abspath(os.path.join(base_dir, owner_login))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok = True)
    target_file = os.path.join(target_dir, repository_name + '.zip')
    if os.path.exists(target_file):
        return target_file
    max_retry = retry
    while retry >= 0:
        try:
            redirect_response = requests.get(github_base_url + '/repos/' + owner_login + '/' + repository_name + '/zipball', headers = gh_header, timeout = (30, 30), allow_redirects = False)
            Log.info(redirect_response.request.url)
            if redirect_response.status_code == 302 or redirect_response.status_code == 301:
                response = requests.get(redirect_response.headers['Location'], headers = gh_header, timeout = (30, 120), allow_redirects = False)
            elif redirect_response.status_code == 200:
                response = redirect_response
            elif redirect_response.status_code == 403:
                if retry > 0:
                    wait_time = (max_retry - retry + 1) * 10
                    Log.warn('[Retry] GitHub API limitation due to http status ' + str(redirect_response.status_code) + ', retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                    retry = retry - 1
                    time.sleep(wait_time)
                    continue
                else:
                    break
            else:
                Log.error('[Failed] Http status ' + str(redirect_response.status_code))
                break
            if response.status_code == 200:
                Log.info(response.request.url)
                with open(target_file, 'wb') as f:
                    f.write(response.content)
                return target_file
            elif response.status_code == 403:
                if retry > 0:
                    wait_time = (max_retry - retry + 1) * 10
                    Log.warn('[Retry] GitHub API limitation due to http status ' + str(response.status_code) + ', retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                    retry = retry - 1
                    time.sleep(wait_time)
                    continue
                else:
                    break
            else:
                Log.error('[Failed] Http status ' + str(response.status_code))
                break
        except requests.exceptions.ReadTimeout as e:
            Log.error('[Failed] ReadTimeout after 120000ms')
            break
        except requests.exceptions.ConnectionError as e:
            if retry > 0:
                wait_time = (max_retry - retry + 1) * 5
                Log.warn('[Retry] ConnectionError, retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                retry = retry - 1
                time.sleep(wait_time)
                continue
            else:
                break
        except requests.exceptions.RequestException as e:
            if retry > 0:
                wait_time = (max_retry - retry + 1) * 5
                Log.warn('[Retry] RequestException, retry after ' + str(wait_time) + ' secs, remain retry time(s) ' + str(retry))
                retry = retry - 1
                time.sleep(wait_time)
                continue
            else:
                break
    Log.error('Download repo zipball request failed...')
    if os.path.exists(target_file):
        os.remove(target_file)
    return ''

def rm_repo_zipball(result, base_dir):
    target_dir = os.path.abspath(os.path.join(base_dir, result['owner_login']))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok = True)
    target_file = os.path.join(target_dir, result['repository_name'] + '.zip')
    if os.path.exists(target_file):
        os.remove(target_file)

def rm_owner_dir(owner_login, base_dir):
    target_dir = os.path.abspath(os.path.join(base_dir, owner_login))
    if os.path.exists(target_dir):
        os.rmdir(target_dir)
