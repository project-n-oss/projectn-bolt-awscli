# awscli-plugin-bolt

This AWS CLI plugin provides an authentication and authorization solution for accessing Bolt securely using the AWS CLI.

It uses the standard AWS CLI configuration to store the URL for accessing Bolt. Active profiles disable regular S3 request signing, and instead provide a presigned STS `GetCallerIdentity` API call to securely authenticate requests using Bolt.

## Prerequisites

The minimum supported version of Python is version 3.

`awscli` must be installed. e.g. `pip3 install awscli --user`

## Installation

To install the plugin package, run: `pip3 install awscli-plugin-bolt --user`.

## Configuration

To configure the plugin after it has been installed, use `aws configure`:

```bash
aws configure set plugins.bolt awscli-plugin-bolt
aws [--profile PROFILE] configure set bolt_custom_domain <bolt custom domain>
aws [--profile PROFILE] configure set bolt_az <preferred availability zone ID>
```
`bolt_custom_domain`

For example, to activate a Bolt service using an internal load balancer hosted at `https://bolt.us-east-1.project.n` for the `staging` AWS profile, run:
```bash
aws --profile staging configure set bolt_custom_domain project.n
aws --profile staging configure set bolt_az use1-az1
```

Alternatively, the bolt_url and bolt_hostname can be set explicitly
```bash
aws --profile staging configure set bolt_hostname bolt.us-east-1.project.n
aws --profile staging configure set bolt_url https://quicksilver.us-east-1.project.n
aws --profile staging configure set bolt_az use1-az1
```

## AWS CLI v2

This plugin has been tested for compatibility with [AWS CLI version 2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html), but please take note of the [[plugins] configuration breaking changes](https://docs.aws.amazon.com/cli/latest/userguide/cliv2-migration.html#cliv2-migration-profile-plugins). In particular, you will need to add a block like:

```
[plugins]
cli_legacy_plugin_path = /Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/site-packages
```

in your `~/.aws/config` file for the plugin registration to succeed.

To find the correct location for `cli_legacy_plugin_path` after installing the plugin, run:

```bash
pip3 show awscli-plugin-bolt | grep Location:
```
