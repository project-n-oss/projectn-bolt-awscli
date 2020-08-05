import subprocess
import imp

"""

A simple installer for the awscli_bolt_plugin

"""

# === Bootstrap the installer if it cannot find its dependancies === 
# Pexpect
try:
    imp.find_module('pexpect')
except ImportError:
  print("Installing pexpect dependancy...")
  proc = subprocess.Popen(['pip', 'install', '--user', 'pexpect'])
  out, err = proc.communicate()

  print(out)
  if proc.returncode != 0:
    raise Exception('\'pexpect\' is an installer requirement. Please install using \'pip install pexepect\'')

# Click
try:
    imp.find_module('click')
except ImportError:
  print("Installing click dependancy...")
  proc = subprocess.Popen(['pip', 'install', '--user', 'click'])
  out, err = proc.communicate()

  print(out)
  if proc.returncode != 0:
    raise Exception('\'click\' is an installer requirement. Please install using \'pip install click\'')

print()



import click
import pexpect
import sys

def run_bash_cmd(command_str):
  child = pexpect.spawn('/bin/bash', ['-c', command_str])
  child.logfile =  sys.stdout.buffer 
  child.expect(pexpect.EOF, timeout=None) # Do not timeout command
  child.close()

  if child.signalstatus != None:
    raise Exception('ERROR running command: {}\nInterrupt Signal: {}'.format(command_str, child.signalstatus))
  if child.exitstatus != 0:
    raise Exception('ERROR running command: {}\nExit Code: {}'.format(command_str, child.exitstatus))
  return True

@click.command()
@click.option('--region', prompt='Region', metavar="<region>", help="Region to deploy in")
@click.option('--domain', prompt='Domain', metavar="<domain>", help="BOLT domain")
@click.option('--account_id', prompt='Account ID', metavar="<account id>", help="Account to crunch with")
@click.option('--install_server', prompt='Install Server', metavar="<install server>", help="Install server")
def run(region, domain, account_id, install_server):
  
  cmds = [
    {
      'prompt':"Installing Plugin...",
      'commands':[
        'pip3 install --user .',
        'aws configure set plugins.bolt awscli-plugin-bolt'
      ]
    },

    {
      'prompt':"Configuring plugin to use bolt endpoint with profile..",
      'commands':['aws --profile={} configure set bolt.url https://bolt.{}'.format(region,domain)]
    },

    {
      'prompt':"Allowlist the install server IAM role...",
      'commands':['projectn --profile={} allowlist-principal --project={} {}'.format(region,account_id,install_server)]
    }
  ]

  for batch in cmds:
    click.secho(batch['prompt'], fg='cyan')
    for cmd in batch['commands']:
      click.secho('Running: {}'.format(cmd), fg='cyan')
      run_bash_cmd(cmd)
    click.secho('Complete...\n', fg='green')

  click.secho("Example:", fg="magenta")
  click.secho("Use AWS CLI to access bolt buckets", fg="magenta")
  click.secho('aws --profile={region} s3 ls'.format(region), fg='magenta')

if __name__ == '__main__':
  click.clear()
  try:
    splash = []
    with open("./splash.txt", 'r') as f:
      for line in f:
        splash.append(line.replace('\n',""))
  except:
    print('Warning: Missing splash text')
    splash = ["======== BOLT CLI INSTALLER ========"]
  
  for line in splash:
    click.secho(line,fg='green')
  click.secho("\nFor technical support email: support@projectn.co\n",fg='white')

  run()