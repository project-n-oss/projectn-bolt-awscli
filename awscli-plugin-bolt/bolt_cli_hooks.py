import sys 
from urllib.parse import urlsplit
from botocore.handlers import disable_signing

from .bolt_router import BoltRouter, get_region, get_availability_zone_id

_global_bolt_router = None

def try_activate(parsed_args, **kwargs):
    try:
        _activate(parsed_args, **kwargs)
    except Exception as e:
        print(f"failed to initialize Bolt S3, falling back to S3: {e}", file=sys.stderr)
        return 

def _activate(parsed_args, **kwargs):
    """Activates the Bolt CLI plugin if we are sending an S3 command."""
    if not parsed_args.command.startswith('s3'):
        return
    session = kwargs['session']

    if parsed_args.profile:
        session.set_config_variable('profile', parsed_args.profile)
    profile = session.get_scoped_config()
    
    region = None
    if 'bolt_region' in profile:
        region = profile['bolt_region']
    elif 'region' in profile:
        region = profile['region']
    else:
        try:
            region = get_region()
        except Exception as e:
            pass

    if 'bolt_custom_domain' in profile and region is not None:
        scheme = 'https' 
        service_url = f"quicksilver.{region}.{profile['bolt_custom_domain']}"
        hostname = f"bolt.{region}.{profile['bolt_custom_domain']}"
    elif 'bolt_hostname' in profile and 'bolt_url' in profile:
        hostname = profile['bolt_hostname']
        scheme, service_url, _, _, _ = urlsplit(profile['bolt_url'])
    else:
        # must define either `custom_domain` and 'region' or `hostname` + `url` to activate
        return

    az_id = None
    if 'bolt_az' in profile:
        az_id = profile['bolt_az']
    else:
        try:
            az_id = get_availability_zone_id()
        except Exception as e:
            pass

    global _global_bolt_router
    _global_bolt_router = BoltRouter(scheme, service_url, hostname, az_id)

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

def before_send_hook(*args, **kwargs):
    if _global_bolt_router != None:
        return _global_bolt_router.send(*args, **kwargs)
