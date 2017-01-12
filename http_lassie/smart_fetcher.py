import json
import time
import requests
import traceback
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
    """
    Get a proxy from your mimic (proxy broker) server.

    :param mimic_server: a URL like `http://192.168.99.100:8901`
    :param request_url: the URL you want to request (needed because mimic
        throttles by domain)
    :param requirements: the requirements for the proxy (e.g. anonymous)
    :param max_wait_time: the maximum time you are willing to wait for a
        response before a timeout
    :return: a proxy resource
    """
    params = {'url': request_url, 'max_wait_time': max_wait_time}
    if requirements:
        params['requirements'] = ",".join(requirements)

    resp = requests.post(mimic_server + "/proxies/acquire", data=params)
    assert resp.status_code == 200, resp.content
    return resp.json()


def release_proxy(mimic_server, proxy_resource, resp_time=-1,
                  is_failure=False):
    """
    Release this proxy for use again on mimic.

    :param mimic_server: a URL like `http://192.168.99.100:8901`
    :param proxy_resource: the used proxy resource (returned from `get_proxy`)
    :param resp_time: the total time it took for this response
        (used for weighting which proxies to use in the future)
    :param is_failure: True if the content returned by this proxy was invalid
        (e.g. if their is now a captcha code)
    """
    params = proxy_resource

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
        """

        :param mimic_server: the url to your mimic (proxy broker) server
            (e.g. `http://192.168.99.100:8901`)
        :param splash_server: the url to your SPLASH server
            (e.g. http://192.168.99.100:8050). Can be None (or nonsense)
            if you do not use javascript rendering.
        :param proxy_requirements: the requirements for your proxy request
            to mimic
        :param splash_config: the configuration (parameters) used for
            fulfilling splash (JS-rendering) requests
        :param max_wait_time: the max time to wait before a timeout
        """
        self._mimic_server = mimic_server
        self._splash_server = splash_server
        self._proxy_requirements = proxy_requirements or []
        self._splash_config = splash_config or DEFAULT_SPLASH_CONFIG.copy()
        self._max_wait_time = max_wait_time

    def __call__(self,
                 request_url,
                 request_params=None,
                 request_data=None,
                 http_method='GET',
                 extractor=content_extractor,
                 validator=always_true,
                 render_json=False,
                 splash_overrides=None,
                 header_overrides=None,
                 retries=3):
        """

        :param request_url: the URL you want to fetch
        :param request_params: the parameters to your request (encoded in url)
        :param request_data: the data in your request (for a POST)
        :param http_method: the method to use ('GET' or 'POST')
        :param extractor: the function to call to extract content from the
            response object.
        :param validator: the function to call to validate the extracted
            content before returning
        :param render_json: if True, use splash to render the JS
        :param splash_overrides: a optional dictionary of values to send
            with the splash request
        :param retries: maximum number of retries before failing
        :return: a tuple of (content, success)
        """

        content, resp_time, is_failure = None, -1, True

        while is_failure and retries > 0:
            # Get the proxy to work with.
            proxy_resource = get_proxy(self._mimic_server,
                                       request_url,
                                       self._proxy_requirements,
                                       max_wait_time=self._max_wait_time)
            try:
                headers = {'User-Agent': random_user_agent()}
                if header_overrides:
                    headers.update(header_overrides)

                if render_json:  # Use splash server
                    kwargs = {**self._splash_config,
                              **(splash_overrides or {})}
                    kwargs.update({'proxy': proxy_resource['proxy'].lower(),
                                   'timeout': self._max_wait_time,
                                   'wait': 10,  # Render wait time
                                   'http_method': http_method,
                                   'filters': "nofonts,easylist"})

                    # body but use encoded params
                    if request_params:
                        request_url += "?" + urlencode(request_params)
                    elif request_data:
                        kwargs['body'] = urlencode(request_params)

                    kwargs['url'] = request_url
                    kwargs['headers'] = headers

                    start_time = time.time()
                    resp = requests.post(self._splash_server + '/render.html',
                                         data=json.dumps(kwargs),
                                         headers={"Content-Type": "application/json"})
                else:  # Just use requests
                    kwargs = {'timeout': self._max_wait_time}

                    if proxy_resource['proxy'].startswith('HTTPS'):
                        kwargs['proxies'] = {'https': proxy_resource['proxy']}
                    else:
                        kwargs['proxies'] = {'http': proxy_resource['proxy']}

                    if request_params:
                        kwargs['params'] = request_data
                    if request_data:
                        kwargs['data'] = request_data

                    kwargs['headers'] = headers

                    start_time = time.time()
                    resp = requests.request(http_method, request_url, **kwargs)

                assert resp.status_code == 200, (resp.status_code, resp.content)
                resp_time = time.time() - start_time
                content = extractor(resp)
                is_failure = not validator(content)
            except Exception as e:
                is_failure = True
                retries -= 1
                # TODO: Add better logging
                print("RETRYING {} on {}".format(retries, e))
            finally:
                release_proxy(self._mimic_server, proxy_resource, resp_time,
                              is_failure)

        return content, not is_failure
