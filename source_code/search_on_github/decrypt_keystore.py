import ghsearch
import os
import re
import subprocess
import platform
import hashlib

keystore_base_dir = 'ks_config_result'

store_pwd_pattern = rb'storePassword[\s]*[\(=]?[\s]*[\'"]([\S]*)[\'"][\s]*[\)]?'
key_pwd_pattern = rb'keyPassword[\s]*[\(=]?[\s]*[\'"]([\S]*)[\'"][\s]*[\)]?'
store_pwd_universal_pattern = rb'storePassword[\s]*([\S]*)'
key_pwd_universal_pattern = rb'keyPassword[\s]*([\S]*)'
get_property_var_pattern = r'getProperty[\s]*\([\s]*[\'"]([\S]*)[\'"][\s]*\)'
get_var_pattern = r'get[\s]*\([\s]*[\'"]([\S]*)[\'"][\s]*\)'
get_env_pattern = r'getenv[\s]*\([\s]*[\'"]([\S]*)[\'"][\s]*\)'
value_pattern_part = rb'[\s=:]*([\S]*)'

keytool_list_pattern = r'([\S]*), \b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b [0-9]{1,2}, [0-9]{4}, PrivateKeyEntry,[\s]+Certificate fingerprint \(\b(SHA-512|SHA-384|SHA-256|SHA-1|MD5)\b\): ([A-Z0-9:]*)'
begin_cert = '-----BEGIN CERTIFICATE-----'
end_cert = '-----END CERTIFICATE-----'

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

def cmd_find_file(search_dir, search_pattern):
    return run_command(['find', search_dir, '-name', search_pattern], cwd=search_dir)

# Before use keytool cmds we should change java tool display language to English.
# Use system env: JAVA_TOOL_OPTIONS=-Duser.language=en
def cmd_keytool_list(keystore_file_path, store_pwd):
    return run_command(['/usr/lib/jvm/jdk-21.0.2/bin/keytool', '-list', '-keystore', keystore_file_path, '-storepass', store_pwd], env={'JAVA_TOOL_OPTIONS': '-Duser.language=en'})

def cmd_keytool_list_rfc(keystore_file_path, store_pwd):
    return run_command(['/usr/lib/jvm/jdk-21.0.2/bin/keytool', '-list', '-keystore', keystore_file_path, '-storepass', store_pwd, '-rfc'], env={'JAVA_TOOL_OPTIONS': '-Duser.language=en'})

def get_certificates(ks_list_rfc_result):
    lines = ks_list_rfc_result.split(os.linesep)
    certificates = []
    per_certificate = ''
    is_cert_line = False
    for line in lines:
        if line.startswith(begin_cert):
            is_cert_line = True
            continue
        if line.startswith(end_cert):
            is_cert_line = False
            certificates.append(per_certificate)
            per_certificate = ''
            continue
        if is_cert_line is True:
            per_certificate = per_certificate + line
    return certificates

def get_keystore_alias(keystore_file_path, store_pwd):
    ks_list_result = cmd_keytool_list(keystore_file_path, store_pwd)
    if platform.system() == 'Windows':
        ks_list_result = ks_list_result.decode('gbk')
    else:
        ks_list_result = ks_list_result.decode('utf8')
    if 'java.io.IOException' in ks_list_result:
        return False, None
    else:
        ks_list_rfc_result = cmd_keytool_list_rfc(keystore_file_path, store_pwd)
        if platform.system() == 'Windows':
            ks_list_rfc_result = ks_list_rfc_result.decode('gbk')
        else:
            ks_list_rfc_result = ks_list_rfc_result.decode('utf8')
        key_alias_result = re.findall(keytool_list_pattern, ks_list_result, re.M)
        certificates = get_certificates(ks_list_rfc_result)
        if len(key_alias_result) == len(certificates) and len(key_alias_result) != 0:
            key_alias = []
            for i in range(len(key_alias_result)):
                key_alias.append({
                    'name': key_alias_result[i][0],
                    'hash': key_alias_result[i][3].replace(':', ''),
                    'certificate': certificates[i]
                })
            return True, key_alias
        return False, None

def get_keystore_private_keys(base_dir, repo, keystore_file, store_pwd_list):
    keystore_file_path = ghsearch.get_file_path(base_dir, repo, keystore_file)
    if not os.path.isfile(keystore_file_path):
        return False, None, None
    for store_pwd in store_pwd_list:
        can_decrypt, key_alias = get_keystore_alias(keystore_file_path, store_pwd)
        if can_decrypt:
            return can_decrypt, store_pwd, key_alias
    return False, None, None

def get_keystore_file_hash(base_dir, repo, keystore_file):
    bytes = ghsearch.read_file(base_dir, repo, keystore_file)
    if bytes == '':
        return ''
    readable_hash = hashlib.md5(bytes).hexdigest()
    return readable_hash

def parse_password_direct(base_dir, repo, config_file):
    file_content = ghsearch.read_file(base_dir, repo, config_file)
    if file_content == '':
        return None, None
    
    store_pwd_list = re.findall(store_pwd_pattern, file_content)
    store_pwd = None
    if store_pwd_list:
        store_pwd = list(map(lambda x: x.decode().strip(), store_pwd_list))
    
    key_pwd_list = re.findall(key_pwd_pattern, file_content)
    key_pwd = None
    if key_pwd_list:
        key_pwd = list(map(lambda x: x.decode().strip(), key_pwd_list))
    return store_pwd, key_pwd

def match_variable_value(variable, file_content):
    try:
        value_pattern = re.compile(variable.encode('ascii') + value_pattern_part)
    except re.error as e:
        Log.error(e)
        return None
    value_list = re.findall(value_pattern, file_content)
    if value_list:
        if isinstance(value_list[0], str):
            return value_list[0].decode().strip()
        else:
            return None
    else:
        return None

def search_variable_definition(variable, base_dir, repo, config_file):
    Log.print('search_variable_definition: variable = ' + variable + ', repo = ' + repo + ', config_file = ' + config_file)
    var_search_result = ghsearch.gh_search_code('repo:' + repo + ' ' + variable, retry=1)
    if len(var_search_result) <= 0:
        Log.error('Cannot find variable definition.')
        return None
    if len(var_search_result) > 10:
        Log.error('Too much variable definition results ( > 10 ), skip...')
        return None
    probable_value_other = []
    probable_value_this = []
    find_in_other_file = False
    for per_result in var_search_result:
        if per_result['path'] != config_file:
            Log.info('Probable variable definition in another file...')
            ghsearch.dl_single_result(per_result, base_dir)
            file_content = ghsearch.read_file(base_dir, repo, per_result['path'])
            if file_content == '':
                continue
            value = match_variable_value(variable, file_content)
            if value:
                find_in_other_file = True
                probable_value_other.append(value)
        else:
            Log.info('Probable variable definition in original config file...')
            file_content = ghsearch.read_file(base_dir, repo, config_file)
            if file_content == '':
                continue
            value = match_variable_value(variable, file_content)
            if value:
                probable_value_this.append(value)
    if find_in_other_file:
        return probable_value_other[0]
    else:
        if len(probable_value_this) <= 0:
            return None
        else:
            return probable_value_this[0]

def parse_pwd_pattern(pwd, base_dir, repo, config_file):
    parsed_pwd = []
    for per_pwd in pwd:
        print(per_pwd)
        if '.getProperty(' in per_pwd or '.get(' in per_pwd or 'System.getenv(' in per_pwd:
            if '.getProperty(' in per_pwd:
                pattern = get_property_var_pattern
            elif '.get(' in per_pwd:
                pattern = get_var_pattern
            elif 'System.getenv(' in per_pwd:
                pattern = get_env_pattern
            var = re.findall(pattern, per_pwd)
            if len(var) > 0:
                result = search_variable_definition(var[0], base_dir, repo, config_file)
                if result:
                    parsed_pwd.append(result)
            else:
                Log.error('Invalid getProperty statement format.')
        else:
            result = search_variable_definition(per_pwd, base_dir, repo, config_file)
            if result:
                parsed_pwd.append(result)
    return parsed_pwd

def parse_password_advanced(base_dir, repo, config_file):
    if repo == 'jsroads/mylibs':
        return None, None 
    file_content = ghsearch.read_file(base_dir, repo, config_file)
    if file_content == '':
        return None, None
    
    store_pwd_list = re.findall(store_pwd_universal_pattern, file_content)
    store_pwd = None
    if store_pwd_list:
        store_pwd = list(map(lambda x: x.decode().strip(), store_pwd_list))
    
    key_pwd_list = re.findall(key_pwd_universal_pattern, file_content)
    key_pwd = None
    if key_pwd_list:
        key_pwd = list(map(lambda x: x.decode().strip(), key_pwd_list))
    if store_pwd or key_pwd:
        if store_pwd:
            store_pwd = parse_pwd_pattern(store_pwd, base_dir, repo, config_file)
        if key_pwd:
            key_pwd = parse_pwd_pattern(key_pwd, base_dir, repo, config_file)
    return store_pwd, key_pwd


def scan_ks_file(base_dir, input_file):
    final_result = {}
    ks_config_result = ghsearch.parse_result_from_file(input_file)
    total = len(ks_config_result)
    progress = 0
    start_progess = 0
    end_progress = total
    for per_result in ks_config_result:
        progress = progress + 1
        if progress < start_progess:
            continue
        if progress > end_progress:
            break
        
        fs_ks_config_file_path = ghsearch.get_file_path(base_dir, per_result['repository_full_name'], per_result['path'])
        if not os.path.exists(fs_ks_config_file_path):
            Log.error('[' + str(progress) + '/' + str(total) + '] Keystore config file not exist, skip ' + per_result['repository_full_name'])
            continue
        fs_repo_path = os.path.abspath(os.path.join(base_dir, per_result['repository_full_name']))
        keystore_search_res = cmd_find_file(fs_repo_path, '*.keystore')
        if platform.system() == 'Windows':
            keystore_search_res = keystore_search_res.decode('gbk')
        else:
            keystore_search_res = keystore_search_res.decode('utf8')
        keystore_search_res = keystore_search_res.replace(fs_repo_path + os.path.sep, '')
        keystore_search_res = keystore_search_res.splitlines()

        jks_search_res = cmd_find_file(fs_repo_path, '*.jks')
        if platform.system() == 'Windows':
            jks_search_res = jks_search_res.decode('gbk')
        else:
            jks_search_res = jks_search_res.decode('utf8')
        jks_search_res = jks_search_res.replace(fs_repo_path + os.path.sep, '')
        jks_search_res = jks_search_res.splitlines()

        ks_search_res = keystore_search_res + jks_search_res
        if len(ks_search_res) == 0:
            Log.warn('[' + str(progress) + '/' + str(total) + '] Keystore/jks file not found, skip ' + per_result['repository_full_name'])
            continue
        if per_result['repository_full_name'] in final_result:
            config_file_list = final_result[per_result['repository_full_name']]['config_file_list']
            keystore_file_list = final_result[per_result['repository_full_name']]['keystore_file_list']
            config_file_list.append(per_result['path'])
            keystore_file_list = keystore_file_list + ks_search_res
            final_result[per_result['repository_full_name']]['config_file_list'] = list(set(config_file_list))
            final_result[per_result['repository_full_name']]['keystore_file_list'] = list(set(keystore_file_list))
        else:
            final_result[per_result['repository_full_name']] = {
                    "config_file_list": [ per_result['path'] ],
                    "keystore_file_list": list(set(ks_search_res))
                }
        Log.info('[' + str(progress) + '/' + str(total) + '] Repo scan success ' + per_result['repository_full_name'])
            
    print('Get ' + str(len(final_result)) + ' valid repository results.')
    return final_result


def decrypt(base_dir, ks_result_with_repo, success_output_file, failed_output_file):
    keystore_result = []
    undecrypted_keystore_result = []
    key_sha256_lists = []
    progress = 0
    total = len(ks_result_with_repo.keys())
    for repo_key in ks_result_with_repo.keys():
        progress = progress + 1
        
        repo_item = ks_result_with_repo[repo_key]
        config_file_list = repo_item['config_file_list']
        keystore_file_list = repo_item['keystore_file_list']

        store_pwd_list = []
        key_pwd_list = []

        is_advanced_dec = False

        for config_file in config_file_list:
            store_pwd, key_pwd = parse_password_direct(base_dir, repo_key, config_file)
            if store_pwd or key_pwd:
                is_advanced_dec = False
                if store_pwd:
                    store_pwd_list = store_pwd_list + store_pwd
                if key_pwd:
                    key_pwd_list = key_pwd_list + key_pwd
            # else:
            #     store_pwd, key_pwd = parse_password_advanced(base_dir, repo_key, config_file)
            #     if store_pwd or key_pwd:
            #         is_advanced_dec = True
            #         Log.info('========== Find password from parse_password_advanced ==========')
            #         if store_pwd:
            #             store_pwd_list = store_pwd_list + store_pwd
            #         if key_pwd:
            #             key_pwd_list = key_pwd_list + key_pwd
        
        store_pwd_list = list(set(store_pwd_list))
        key_pwd_list = list(set(key_pwd_list))

        advanced_dec_count = 0

        for keystore_file in keystore_file_list:
            keystore_file_hash = get_keystore_file_hash(base_dir, repo_key, keystore_file)
            if len(store_pwd_list) != 0 and len(key_pwd_list) != 0 and keystore_file_hash != '':
                print(store_pwd_list)
                can_decrypt, correct_store_pwd, key_alias = get_keystore_private_keys(base_dir, repo_key, keystore_file, store_pwd_list)
                if can_decrypt:
                    keystore_result.append({
                        'repo': repo_key,
                        'keystore_file': keystore_file,
                        'keystore_file_hash': keystore_file_hash,
                        'store_pwd': correct_store_pwd,
                        'key_alias': key_alias,
                        'key_pwd_list': key_pwd_list,
                    })
                    key_sha256_lists = key_sha256_lists + list(map(lambda x: x['hash'], key_alias))
                    Log.info('[' + str(progress) + '/' + str(total) + '] Decrypt keystore file: ' + keystore_file + ' in repo: ' + repo_key)
                    if is_advanced_dec == True:
                        advanced_dec_count = advanced_dec_count + 1
                    continue
                else:
                    Log.error('[' + str(progress) + '/' + str(total) + '] Cannot decrypt keystore file: ' + keystore_file + ' in repo: ' + repo_key)
            else:
                Log.error('[Failed] No valid store or key password found in ' + keystore_file + ' in repo: ' + repo_key)
            undecrypted_keystore_result.append({
                'repo': repo_key,
                'keystore_file': keystore_file,
                'keystore_file_hash': keystore_file_hash,
            })

    key_sha256_lists = list(set(key_sha256_lists))
    print('Total key cert hash: ' + str(len(key_sha256_lists)))
    ghsearch.write_result_to_file(keystore_result, success_output_file)
    print('Write ' + str(len(keystore_result)) + ' decrypted keystore results.')
    
    ghsearch.write_result_to_file(undecrypted_keystore_result, failed_output_file)
    print('Write ' + str(len(undecrypted_keystore_result)) + ' undecrypted keystore results.')
    # print('Decrypted by parse_password_advanced: ' + str(len(is_advanced_dec)))
    return keystore_result

def process(ks_config_file, ks_result_dec, ks_result_enc):
    ks_result_with_repo = scan_ks_file(keystore_base_dir, ks_config_file)
    decrypt(keystore_base_dir, ks_result_with_repo, ks_result_dec, ks_result_enc)

 