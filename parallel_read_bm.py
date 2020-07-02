# Runs benchmarks on reads from S3 and Bolt using the AWS CLI plugin
#
# Assumed to be running in an environment where the the AWS CLI has the bolt plugin installed,
# with two profiles set up, one using the bolt plugin, and one without.
#
# Benchmark must be run in the same VPC/peered VPC of the Bolt instance to test

from multiprocessing import Pool, cpu_count
from subprocess import run, DEVNULL
from time import time
from functools import partial
from argparse import ArgumentParser
from boto3 import client

parser = ArgumentParser('bm')
parser.add_argument('--bucket', type=str, default='sr-sqs-test-bucket', help='s3 bucket to benchmark')
parser.add_argument('--max_keys', type=int, default=10, help='max number of keys to fetch')
parser.add_argument('--pool_size', type=int, default=cpu_count(), help='size of worker pool (defaults to CPU count)')
parser.add_argument('--s3_profile', type=str, default='default', help='AWS profile used to make calls to S3')
parser.add_argument('--bolt_profile', type=str, default='bolt', help='AWS profile used to make calls to Bolt')
parser.add_argument('--read_timeout', type=int, default=30, help='time in seconds to wait for a single read operation to finish')
flags = parser.parse_args()

client = client('s3')


def get_obj(prof, key):
    return run(['aws', '--profile', prof, 's3', 'cp', 's3://{}/{}'.format(flags.bucket, key), '/tmp/'], stdout=DEVNULL)


if __name__ == '__main__':
    print("""Listing bucket {}
Max keys:  {}
Pool size: {}""".format(flags.bucket, flags.max_keys, flags.pool_size))

    # fetch list of keys to benchmark from S3
    response = client.list_objects_v2(
        Bucket=flags.bucket, MaxKeys=flags.max_keys)
    if "Contents" not in response or len(response["Contents"]) == 0:
        print("No content in list response")
        exit(1)
    keys = list(map(lambda c: c["Key"], response["Contents"]))

    # run benchmarks with both profiles
    for profile in (flags.s3_profile, flags.bolt_profile):
        f = partial(get_obj, profile)

        # perform reads in parallel using a Python multiprocessing.Pool
        start = time()
        with Pool(processes=flags.pool_size) as pool:
            multiple_results = [pool.apply_async(f, (key,)) for key in keys]
            [res.get(timeout=flags.read_timeout) for res in multiple_results]
        stop = time()
        print("""Total time {}: {:.3f}s
Keys fetched: {}""".format(profile, (stop - start), response["KeyCount"]))
