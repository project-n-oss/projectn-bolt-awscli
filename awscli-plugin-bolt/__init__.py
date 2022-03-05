from collections import defaultdict
import json
from random import choice
from urllib.parse import urlsplit, urlunsplit

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import UnknownEndpointError
from botocore.handlers import disable_signing
from botocore.session import get_session
from urllib3 import PoolManager


class Bolt:
    """A stateful request mutator for Bolt S3 proxy.

    Sends S3 requests to an alternative Bolt URL based on configuration.

    To set a Bolt S3 proxy URL, run `aws [--profile PROFILE] configure set bolt.url http://localhost:9000`.
    """

    # Whether Bolt is active in the command context.
    active = False
    # The scheme (parsed at bootstrap from the AWS config).
    scheme = None
    # The service discovery host (parsed at bootstrap from the AWS config).
    service_url = None
    # Availability zone ID to use (may be none)
    az_id = None
    # Map of Bolt endpoints to use for connections
    bolt_endpoints = defaultdict(list)
    # const ordering to use when selecting endpoints
    PREFERRED_READ_ENDPOINT_ORDER = ("main_read_endpoints", "main_write_endpoints", "failover_read_endpoints", "failover_write_endpoints")
    PREFERRED_WRITE_ENDPOINT_ORDER = ("main_write_endpoints", "failover_write_endpoints")


    @staticmethod
    def activate(parsed_args, **kwargs):
        """Activates the Bolt CLI plugin if we are sending an S3 command."""
        if not parsed_args.command.startswith('s3'):
            return
        session = kwargs['session']

        if parsed_args.profile:
            session.set_config_variable('profile', parsed_args.profile)
        profile = session.get_scoped_config()

        # Activate the Bolt scheme only if a bolt.url config is provided.
        if 'bolt' not in profile or 'url' not in profile['bolt']:
            return

        Bolt.active = True
        Bolt.scheme, Bolt.service_url, _, _, _ = urlsplit(profile['bolt']['url'])
        if 'az' in profile['bolt']:
            Bolt.az_id = profile['bolt']['az']
        # TODO: support other methods of selecting AZ

        Bolt.get_endpoints()
        # Disable request signing. We will instead send a presigned authenticating request as a request header to Bolt.
        session.register(
            'choose-signer', disable_signing, unique_id='bolt-disable-signing')

        # We always use path style addressing instead of VirtualHost style addressing.
        # This ensures e.g. ListBucket for bucket foo will be sent as:
        #
        # GET /foo
        # Host: <bolt URL>
        #
        # as opposed to:
        #
        # GET /
        # Host: foo.<bolt URL>
        if profile.get('s3') is None:
            profile['s3'] = {}
        profile['s3']['addressing_style'] = 'path'

    @staticmethod
    def send(**kwargs):
        if not Bolt.active:
            return
        # Dispatches to the configured Bolt scheme and host.
        prepared_request = kwargs['request']
        _, _, path, query, fragment = urlsplit(prepared_request.url)
        host = Bolt.select_endpoint(prepared_request.method)

        prepared_request.url = urlunsplit((Bolt.scheme, host, path, query, fragment))

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

    @staticmethod
    def get_endpoints():
        try:
            service_url = f'{Bolt.service_url}/services/bolt?az={Bolt.az_id}'
            resp = PoolManager(timeout=3.0).request('GET', service_url, retries=2)
            endpoint_map = json.loads(resp.data.decode('utf-8'))
            Bolt.bolt_endpoints = defaultdict(list, endpoint_map)
        except Exception as e:
            raise e

    @staticmethod
    def select_endpoint(method):
        preferred_order = Bolt.PREFERRED_READ_ENDPOINT_ORDER if method in {"GET", "HEAD"} else Bolt.PREFERRED_WRITE_ENDPOINT_ORDER
        for endpoints in preferred_order:
            if Bolt.bolt_endpoints[endpoints]:
                # use random choice for load balancing
                return f"{choice(Bolt.bolt_endpoints[endpoints])}:9000"
        # if we reach this point, no endpoints are available
        raise UnknownEndpointError(service_name='bolt', region_name=Bolt.az_id)



def awscli_initialize(cli):
    """Initializes the AWS CLI plugin for Bolt."""
    # Activate Bolt as soon as the profile is parsed.
    # At this point we know if we're handling an S3 command, and can enable/configure the Bolt integration accordingly.
    cli.register_first('top-level-args-parsed', Bolt.activate)
    # Before we send a request, reroute the request and append a presigned URL for AWS authentication.
    cli.register_last('before-send.s3', Bolt.send)
