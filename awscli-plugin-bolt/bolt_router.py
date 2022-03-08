from collections import defaultdict
import json
from os import environ
from random import choice
from urllib.parse import urlsplit, urlunsplit
from urllib3 import PoolManager
from threading import Lock

import sys 
import sched
import time
from functools import wraps
from threading import Thread


from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import UnknownEndpointError
from botocore.session import get_session
from botocore.httpsession import URLLib3Session

# throws Exception if not found
def get_region():
    region = environ.get('AWS_REGION')
    if region is not None:
        return region
    
    return _default_get('http://169.254.169.254/latest/meta-data/placement/region')

# throws Exception if not found
def get_availability_zone_id():
    zone = environ.get('AWS_ZONE_ID')
    if zone is not None:
        return zone
    
    return _default_get('http://169.254.169.254/latest/meta-data/placement/availability-zone-id')


def _default_get(url):
    try:
        http = PoolManager(timeout=3.0)
        resp = http.request('GET', url, retries=2)
        return resp.data.decode('utf-8')
    except Exception as e:
        raise e


def async_function(func):
    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = Thread(daemon=True, target=func, args=args, kwargs=kwargs)
        func_hl.start()

        return func_hl
    return async_func


def schedule(interval):
    def decorator(func):
        def periodic(scheduler, interval, action, actionargs=()):
            scheduler.enter(interval, 1, periodic,
                            (scheduler, interval, action, actionargs))
            action(*actionargs)

        @wraps(func)
        def wrap(*args, **kwargs):
            scheduler = sched.scheduler(time.time, time.sleep)
            periodic(scheduler, interval, func)
            scheduler.run()
        return wrap
    return decorator

class BoltSession(URLLib3Session):
    """
    We need to override the default behavior of the URLLib3Session class to accept a different hostname for SSL verification,
    since we want to connect to a specific IP without relying on DNS. See https://urllib3.readthedocs.io/en/latest/advanced-usage.html#custom-sni-hostname
    """
    def __init__(self, bolt_hostname, **kwargs):
        self._bolt_hostname = bolt_hostname
        super().__init__(**kwargs)


    def _get_pool_manager_kwargs(self, **extra_kwargs):
        # Add 'server_hostname' arg to use for SSL validation
        extra_kwargs.update(server_hostname=self._bolt_hostname)
        return super()._get_pool_manager_kwargs(**extra_kwargs)


    def send(self, request):
        request.headers['Host'] = self._bolt_hostname
        return super().send(request)
            
class BoltRouter:
    """A stateful request mutator for Bolt S3 proxy.

    Sends S3 requests to an alternative Bolt URL based on configuration.

    To set a Bolt S3 proxy URL, run `aws [--profile PROFILE] configure set bolt.url http://localhost:9000`.
    """

    # const ordering to use when selecting endpoints
    PREFERRED_READ_ENDPOINT_ORDER = ("main_read_endpoints", "main_write_endpoints", "failover_read_endpoints", "failover_write_endpoints")
    PREFERRED_WRITE_ENDPOINT_ORDER = ("main_write_endpoints", "failover_write_endpoints")

    def __init__(self, scheme, service_url, hostname, az_id, update_interval=-1):
        # The scheme (parsed at bootstrap from the AWS config).
        self._scheme = scheme
        # The service discovery host (parsed at bootstrap from the AWS config).
        self._service_url = service_url
        # the hostname to use for SSL validation when connecting directly to Bolt IPs
        self._hostname = hostname
        # Availability zone ID to use (may be none)
        self._az_id = az_id

        # Map of Bolt endpoints to use for connections, and mutex protecting it
        self._bolt_endpoints = defaultdict(list)
        self._mutex = Lock()

        self._get_endpoints()

        if update_interval > 0:
            @async_function
            @schedule(update_interval)
            def update_endpoints():
                try: 
                    self._get_endpoints()
                except Exception as e:
                    print(e, file=sys.stderr, flush=True)
            update_endpoints()

    def send(self, *args, **kwargs):
        # Dispatches to the configured Bolt scheme and host.
        prepared_request = kwargs['request']
        _, _, path, query, fragment = urlsplit(prepared_request.url)
        host = self._select_endpoint(prepared_request.method)

        prepared_request.url = urlunsplit((self._scheme, host, path, query, fragment))

        request = AWSRequest(
          method='POST',
          url='https://sts.amazonaws.com/',
          data='Action=GetCallerIdentity&Version=2011-06-15',
          params=None,
          headers=None
        )
        SigV4Auth(get_session().get_credentials().get_frozen_credentials(), "sts", 'us-east-1').add_auth(request)

        for key in ["X-Amz-Date", "Authorization", "X-Amz-Security-Token"]:
          if request.headers.get(key):
            prepared_request.headers[key] = request.headers[key]
        
        # send this request with our custom session options
        # if an AWSResponse is returned directly from a `before-send` event handler function, 
        # botocore will use that as the response without making its own request.
        return BoltSession(self._hostname).send(prepared_request)

    def _get_endpoints(self):
        try:
            service_url = f'{self._service_url}/services/bolt?az={self._az_id}'
            resp = _default_get(service_url)
            endpoint_map = json.loads(resp)
            with self._mutex: 
                self._bolt_endpoints = defaultdict(list, endpoint_map)
        except Exception as e:
            raise e

    def _select_endpoint(self, method):
        preferred_order = self.PREFERRED_READ_ENDPOINT_ORDER if method in {"GET", "HEAD"} else self.PREFERRED_WRITE_ENDPOINT_ORDER
        
        with self._mutex: 
            for endpoints in preferred_order:
                if self._bolt_endpoints[endpoints]:
                    # use random choice for load balancing
                    return choice(self._bolt_endpoints[endpoints])
        # if we reach this point, no endpoints are available
        raise UnknownEndpointError(service_name='bolt', region_name=self._az_id)

