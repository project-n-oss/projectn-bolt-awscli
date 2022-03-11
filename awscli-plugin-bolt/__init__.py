from .bolt_cli_hooks import try_activate, before_send_hook

def awscli_initialize(cli):
    """Initializes the AWS CLI plugin for Bolt."""
    # Activate Bolt as soon as the profile is parsed.
    # At this point we know if we're handling an S3 command, and can enable/configure the Bolt integration accordingly.
    cli.register_first('top-level-args-parsed', try_activate)
    # Before we send a request, reroute the request and append a presigned URL for AWS authentication.
    cli.register_last('before-send.s3', before_send_hook)
