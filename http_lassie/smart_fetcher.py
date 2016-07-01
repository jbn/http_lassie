import time
import requests
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
from http_lassie.user_agents import random_user_agent


###############################################################################
#                    __                   __                _                 #
#                   / /  _____      __   / /  _____   _____| |                #
#                  / /  / _ \ \ /\ / /  / /  / _ \ \ / / _ \ |                #
#                 / /__| (_) \ V  V /  / /__|  __/\ V /  __/ |                #
#                 \____/\___/ \_/\_/   \____/\___| \_/ \___|_|                #
#                                                                             #
###############################################################################

def get_proxy(mimic_server, request_url, requirements, max_wait_time=60):
    params = {'url': request_url, 'max_wait_time': max_wait_time}
    if requirements:
        params['requirements'] = ",".join(requirements)

    resp = requests.post(mimic_server + "/proxies/acquire", data=params)
    assert resp.status_code == 200, resp.content
    return resp.json()


def release_proxy(mimic_server, proxy_resource, resp_time=-1, is_failure=False):
    params = proxy_resource  # I.e. what you got from get_proxy

    if is_failure:
        params['is_failure'] = 'true'
    if resp_time >= 0:
        params['response_time'] = resp_time

    resp = requests.post(mimic_server + "/proxies/release", data=params)
    assert resp.status_code == 200, resp.content


###############################################################################
#                        _       _         __                _                #
#                  /\  /(_) __ _| |__     / /  _____   _____| |               #
#                 / /_/ / |/ _` | '_ \   / /  / _ \ \ / / _ \ |               #
#                / __  /| | (_| | | | | / /__|  __/\ V /  __/ |               #
#                \/ /_/ |_|\__, |_| |_| \____/\___| \_/ \___|_|               #
#                          |___/                                              #
###############################################################################


DEFAULT_SPLASH_CONFIG = {'timeout': 60, 'wait': 10, 'images': 0}


def diagnostic_extractor(resp):
    print(resp.status_code)
    print(resp.content)
    return resp.content


def content_extractor(resp):
    return resp.content


def json_extractor(resp):
    return resp.json()


def always_true(_):
    return True


class SmartFetcher:
    def __init__(self, mimic_server, splash_server, proxy_requirements=None,
                 splash_config=None, max_wait_time=60):
        self._mimic_server = mimic_server
        self._splash_server = splash_server
        self._proxy_requirements = proxy_requirements or []
        self._splash_config = splash_config or DEFAULT_SPLASH_CONFIG.copy()
        self._max_wait_time = 60

    def __call__(self,
                 request_url,
                 request_params=None,
                 request_data=None,
                 http_method='GET',
                 extractor=content_extractor,
                 validator=always_true,
                 render_json=False,
                 splash_overrides=None,
                 retries = 3):
        splash_config = {**self._splash_config, **(splash_overrides or {})}

        content, resp_time, is_failure = None, -1, True

        # Get the proxy to work with.
        proxy_resource = get_proxy(self._mimic_server,
                                   request_url,
                                   self._proxy_requirements,
                                   max_wait_time=self._max_wait_time)

        while is_failure and retries > 0:
            try:
                headers = {'User-Agent':random_user_agent()}
                if render_json:
                    kwargs = {'proxy': proxy_resource['proxy'].lower(),
                              'timeout': self._max_wait_time,
                              'wait': 10,  # Render wait time
                              'http_method': http_method}

                    # body but use encoded params
                    if request_params:
                        request_url += "?" + urlencode(request_params)

                    if request_data:
                        kwargs['body'] = urlencode(request_params)

                    kwargs['url'] = request_url
                    user_agent = random_user_agent()

                    start_time = time.time()
                    resp = requests.get(self._splash_server + '/render.html',
                                        params=kwargs, headers=headers)
                else:
                    kwargs = {'timeout': self._max_wait_time}
                    kwargs['headers'] = headers

                    if proxy_resource['proxy'].startswith('HTTPS'):
                        kwargs['proxies'] = {'https': proxy_resource['proxy']}
                    else:
                        kwargs['proxies'] = {'http': proxy_resource['proxy']}

                    if request_params:
                        kwargs['params'] = request_data
                    if request_data:
                        kwargs['data'] = request_data

                    start_time = time.time()
                    resp = requests.request(http_method, request_url, **kwargs)

                assert resp.status_code == 200, (resp.status_code, resp.content)
                resp_time = time.time() - start_time
                content = extractor(resp)
                is_failure = not validator(content)
            except Exception as e:
                is_failure = True
                retries -= 1
                print("RETRYING {} on {}".format(retries, e))
            finally:
                release_proxy(self._mimic_server, proxy_resource, resp_time,
                              is_failure)

        return content
