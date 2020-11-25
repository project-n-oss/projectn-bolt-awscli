from urllib.parse import urlsplit, urlunsplit

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.handlers import disable_signing
from botocore.session import get_session


class Bolt:
    """A stateful request mutator for Bolt S3 proxy.

    Sends S3 requests to an alternative Bolt URL based on configuration.

    To set a Bolt S3 proxy URL, run `aws [--profile PROFILE] configure set bolt.url http://localhost:9000`.
    """

    # Whether Bolt is active in the command context.
    active = False
    # The scheme (parsed at bootstrap from the AWS config).
    scheme = None
    # The host (parsed at bootstrap from the AWS config).
    host = None

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
        Bolt.scheme, Bolt.host, _, _, _ = urlsplit(profile['bolt']['url'])

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
        prepared_request.url = urlunsplit((Bolt.scheme, Bolt.host, path, query, fragment))

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


def awscli_initialize(cli):
    """Initializes the AWS CLI plugin for Bolt."""
    # Activate Bolt as soon as the profile is parsed.
    # At this point we know if we're handling an S3 command, and can enable/configure the Bolt integration accordingly.
    cli.register_first('top-level-args-parsed', Bolt.activate)
    # Before we send a request, reroute the request and append a presigned URL for AWS authentication.
    cli.register_last('before-send.s3', Bolt.send)
