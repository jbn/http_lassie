import json
import time
import requests
import sys
from http_lassie.user_agents import random_user_agent
from six.moves.urllib.parse import urlencode

###############################################################################
#                    __                   __                _                 #
#                   / /  _____      __   / /  _____   _____| |                #
#                  / /  / _ \ \ /\ / /  / /  / _ \ \ / / _ \ |                #
#                 / /__| (_) \ V  V /  / /__|  __/\ V /  __/ |                #
#                 \____/\___/ \_/\_/   \____/\___| \_/ \___|_|                #
#                                                                             #
###############################################################################


class FailingStatusCode(Exception):
    def __init__(self, status_code, resp_content, indent=''):
        self.indent = indent
        self.status_code = status_code
        self.resp_content = resp_content

    def __str__(self):
        try:
            if self.resp_content.startswith(b"{"):
                json_body = json.loads(self.resp_content.decode())
                err_doc = json.dumps(json_body, indent='    ')
                lines = err_doc.splitlines()
                return (lines[0] + "\n" +
                        "\n".join(self.indent + line for line in lines[1:]))
            else:
                return ("status code: {}\n".format(self.status_code) +
                        self.indent + "{}".format(self.resp_content))
        except Exception as e:
            return "ERROR PRINTING ERROR on {}".format(e)


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
        # Must be positive! XXX: BUG
        params['response_time'] = resp_time
    else:
        print("RESP TIME: {}".format(resp_time))

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

EXCEPTION_MSG = """
Request exception:
    Request url:  {}
    Retries left: {}
    Type:         {}
    Value:        {}
    Location:     {}:{}
""".strip()


def format_exception(url, retries_left, exc_info):
    exc_type, exc_value, exc_traceback = exc_info
    line = exc_traceback.tb_lineno
    file_name = exc_traceback.tb_frame.f_code.co_filename
    return EXCEPTION_MSG.format(url, retries_left,
                                exc_type, exc_value, file_name, line)


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
                 render_js=False,
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
        :param render_js: if True, use splash to render the JS
        :param splash_overrides: a optional dictionary of values to send
            with the splash request
        :param retries: maximum number of retries before failing
        :return: a tuple of (content, success)
        """

        content, resp_time, is_failure = None, 60, True

        while is_failure and retries > 0:
            proxy_resource, status_received = None, None

            try:
                proxy_resource = self._get_proxy_resource(request_url)
                headers = self._common_headers(header_overrides)

                f = self._via_splash if render_js else self._via_requests
                start_time, resp = f(headers,
                                     http_method,
                                     request_url,
                                     request_params,
                                     request_data,
                                     proxy_resource,
                                     **(splash_overrides or {}))

                resp_time = time.time() - start_time
                content = extractor(resp)
                status_received = resp.status_code

                if resp.status_code == 404 or resp.status_code == 500:
                    is_failure = True
                    release_proxy(self._mimic_server,
                                  proxy_resource,
                                  resp_time,
                                  False)
                    break
                else:
                    if resp.status_code != 200:
                        raise FailingStatusCode(resp.status_code,
                                                resp.content,
                                                indent=' '*18)
                    is_failure = not validator(content)
            except Exception as e:
                is_failure = True
                retries -= 1
                print(format_exception(request_url,
                                       retries,
                                       sys.exc_info()) + "\n\n")
                # TODO: Add better logging
            finally:
                # BUG BUG BUB
                release_proxy(self._mimic_server, proxy_resource, resp_time,
                              is_failure)

        return content, not is_failure

    def _get_proxy_resource(self, request_url):
        resource = get_proxy(self._mimic_server,
                             request_url,
                             self._proxy_requirements,
                             max_wait_time=self._max_wait_time)

        if resource['proxy'] is None:
            time.sleep(60)
            raise Exception('No proxy found')

        return resource

    def _common_headers(self, header_overrides):
        headers = {'User-Agent': random_user_agent()}
        if header_overrides:
            headers.update(header_overrides)
        return headers

    def _via_splash(self, headers, http_method, request_url, request_params,
                    request_data, proxy_resource, **splash_overrides):
        kwargs = {**self._splash_config,
                  **(splash_overrides or {})}
        kwargs.update({'proxy': proxy_resource['proxy'].lower(),
                       # 'timeout': self._max_wait_time,
                       #'wait': 10,  # Render wait time
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
        return start_time, resp

    def _via_requests(self, headers, http_method, request_url,
                      request_params, request_data, proxy_resource,
                      **kwargs):
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

        return start_time, resp
