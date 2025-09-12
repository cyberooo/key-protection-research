import ghsearch
import os
import subprocess
import shutil
import zipfile
import csv
import re
import sys

start_progess = 0
end_progress = 99999
process_number = 0

path_in_html_url_pattern = r'blob/[0-9a-f]+/([\S]+)'

keystore_base_dir = 'ks_config_result'
signing_configs_search_key = 'signingConfigs keyAlias storeFile storePassword keyPassword extension:gradle'
owner_deny_list = []

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

def run_command(cmds, cwd='.', env={}):
    return subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env).communicate()[0]

def cmd_unzip_one_file(target_zip_file, target_file, to_path):
    return run_command(['unzip', '-j', '-o', target_zip_file, target_file, '-d', to_path])

def get_keystore_file(ks_config_result):
    keystore_anaylze_tmp_dir = 'ks_repo_anaylze_tmp_' + str(process_number)
    total = len(ks_config_result)
    progress = 0
    if not os.path.exists(keystore_anaylze_tmp_dir):
        os.makedirs(keystore_anaylze_tmp_dir, exist_ok = True)

    # cached_decrypted = ghsearch.parse_result_from_file('keystore_result_decrypted_all.json')
    # cached_decrypted_repo = list(map(lambda x: x['repo'], cached_decrypted))

    # cached_undecrypted = ghsearch.parse_result_from_file('keystore_result_undecrypted_all.json')
    # cached_undecrypted_repo = list(map(lambda x: x['repo'], cached_undecrypted))

    # cached_all = ghsearch.parse_result_from_file('ks_config_20230505.json')
    # cached_all_html_url = list(map(lambda x: x['html_url'], cached_all))

    ks_results = []
    valid_ks_config_results = []
    # valid_ks_config_ext_results = []
    network_error_results = []

    html_cache = []

    for per_result in ks_config_result:
        progress = progress + 1
        if progress < start_progess:
            html_cache.append(per_result['repository_html_url'])
            continue
        if progress > end_progress:
            break
        if per_result['owner_login'] in owner_deny_list:
            Log.warn('[' + str(progress) + '/' + str(total) + '] Skip repo ' + per_result['repository_html_url'])
            continue
        if per_result['repository_html_url'] in html_cache:
            Log.warn('[' + str(progress) + '/' + str(total) + '] Repo in cache ' + per_result['repository_html_url'])
            continue
        # if per_result['html_url'] in cached_all_html_url:
        #     Log.warn('[' + str(progress) + '/' + str(total) + '] Repo has already processed on last work ' + per_result['repository_html_url'])
        #     continue
        # if per_result['repository_full_name'] in cached_decrypted_repo:
        #     Log.warn('[' + str(progress) + '/' + str(total) + '] Repo has already decrypted on last work ' + per_result['repository_html_url'])
        #     continue
        print('[' + str(progress) + '/' + str(total) + '] Anaylze repo ' + per_result['repository_html_url'])
        # Prepare local tmp dir
        local_repo_dir = os.path.join(keystore_anaylze_tmp_dir, per_result['owner_login'])
        if not os.path.exists(local_repo_dir):
            os.makedirs(local_repo_dir, exist_ok = True)
        
        local_repo_file = ghsearch.dl_result_repo(per_result, keystore_anaylze_tmp_dir)

        # Check if downloaded repo archive file is exist
        if local_repo_file == '':
            Log.error('No such file on local file system... skip this repo: ' + per_result['repository_html_url'])
            network_error_results.append(per_result)
            shutil.rmtree(local_repo_dir)
            continue
        if not os.path.exists(local_repo_file):
            Log.error('No such file on local file system... skip this repo: ' + per_result['repository_html_url'])
            network_error_results.append(per_result)
            shutil.rmtree(local_repo_dir)
            continue

        # Get file info from repo archive file
        local_repo_file_zip = zipfile.ZipFile(local_repo_file)
        repo_file_info = local_repo_file_zip.namelist()
        if len(repo_file_info) == 0:
            Log.error('Zip archive is empty... skip this repo: ' + per_result['repository_html_url'])
            continue
        in_zip_dir_name = repo_file_info[0]
        
        per_ks_result = []
        per_ks_config_ext_result = []
        for per_repo_file_info in repo_file_info:
            if per_repo_file_info.endswith(per_result['path']) or per_repo_file_info.endswith('.keystore') or per_repo_file_info.endswith('.jks'):
                try:
                    path = per_repo_file_info.replace(in_zip_dir_name, '')
                    fake_dir, target_file_name = os.path.split(path)
                    # Prepare tmp dir
                    tmp_file_dir = os.path.abspath(os.path.join(os.path.join(local_repo_dir, per_result['repository_name']), fake_dir))
                    if not os.path.exists(tmp_file_dir):
                        os.makedirs(tmp_file_dir, exist_ok = True)
                    tmp_file_path = os.path.join(tmp_file_dir, target_file_name)
                    # Extract file first
                    print(cmd_unzip_one_file(local_repo_file, per_repo_file_info, tmp_file_dir))
                
                    # Prepare internal dir of keystore base dir
                    fs_file_path = ghsearch.get_file_path(keystore_base_dir, per_result['repository_full_name'], path)
                    fs_file_dir, fs_file_name = os.path.split(fs_file_path)
                    if not os.path.exists(fs_file_dir):
                        os.makedirs(fs_file_dir, exist_ok = True)
                    # Copy file to keystore base dir
                    shutil.copyfile(tmp_file_path, fs_file_path)
                    # Log keystore result
                    if per_repo_file_info.endswith('.keystore') or per_repo_file_info.endswith('.jks'):
                        per_ks_result.append({
                            'name': target_file_name,
                            'path': path,
                            'html_url': per_result['html_url'].replace(per_result['path'], path),
                            'repository_name': per_result['repository_name'],
                            'repository_full_name': per_result['repository_full_name'],
                            'repository_html_url': per_result['repository_html_url'],
                            'owner_login': per_result['owner_login'],
                            'owner_html_url': per_result['owner_html_url']
                        })
                    # Log config result
                    # elif per_repo_file_info.endswith('.gradle') or per_repo_file_info.endswith('.properties'):
                    #     per_ks_config_ext_result.append({
                    #         'name': target_file_name,
                    #         'path': path,
                    #         'html_url': per_result['html_url'].replace(per_result['path'], path),
                    #         'repository_name': per_result['repository_name'],
                    #         'repository_full_name': per_result['repository_full_name'],
                    #         'repository_html_url': per_result['repository_html_url'],
                    #         'owner_login': per_result['owner_login'],
                    #         'owner_html_url': per_result['owner_html_url']
                    #     })
                except BaseException as e:
                    Log.error(e)

        shutil.rmtree(local_repo_dir)
        if len(per_ks_result) != 0:
            ks_results = ks_results + per_ks_result
            # valid_ks_config_ext_results = valid_ks_config_ext_results + per_ks_config_ext_result
            valid_ks_config_results.append(per_result)
            print('[' + str(progress) + '/' + str(total) + '] Found ' + str(len(per_ks_result)) + ' keystore/jks file(s) in ' + per_result['repository_html_url'])
        else:        
            Log.warn('[' + str(progress) + '/' + str(total) + '] No keystore/jks file found in ' + per_result['repository_html_url'])

def parse_siem_result(siem_file, output_file):
    parse_result = []
    with open(siem_file, 'r') as f:
        for siem_row in csv.reader(f):
            if 'basic_info.name' in siem_row[0]:
                continue
            repository_name = siem_row[4].replace(siem_row[7], '', 1).replace('/', '', 1)
            ignored, name = os.path.split(siem_row[6].replace(siem_row[5], '', 1))
            path = siem_row[6].replace(siem_row[5], '', 1)
            path = re.findall(path_in_html_url_pattern, path)[0]
            parse_result.append({
                'name': name,
                'path': path,
                'html_url': siem_row[6],
                'repository_name': repository_name,
                'repository_full_name': siem_row[4],
                'repository_html_url': siem_row[5],
                'owner_login': siem_row[7],
                'owner_html_url': siem_row[8]
            })
    ghsearch.write_result_to_file(parse_result, output_file)
    return parse_result

def process():
    # Step 1: Search keystore config and write result json
    search_policy = [
        (0, 8000, 20),
        (8000, 10000, 10),
        (10000, 20000, 50),
        (20000, 100000, 10000),
        (100000, 384000, 100000)
    ]
    ks_config_result = ghsearch.search_code_full(signing_configs_search_key, search_policy)
    ghsearch.write_result_to_file(ks_config_result, 'ks_config.json')

    # Step 2: Clone repos and get keystore file
    global start_progess
    global end_progress
    global process_number
    start_progess = int(sys.argv[1])
    end_progress = int(sys.argv[2])
    process_number = int(sys.argv[3])
    ks_config_result = ghsearch.parse_result_from_file('ks_config.json')
    get_keystore_file(ks_config_result)

def process_siem(siem_csv, output_file):
    ks_config_result = parse_siem_result(siem_csv, output_file)
    global start_progess
    start_progess = 0
    get_keystore_file(ks_config_result)
