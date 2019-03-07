# zabbix-ipmi-check

Sensors discovery and data gathering script for zabbix

## Usage

```
usage: ipmi_check.py [-h] [-u USERNAME] [-p PASSWORD] [-d] [-t]
                     hostname ipmi_addr

Zabbix IPMI request

positional arguments:
  hostname              Hostname name in zabbix to send data to
  ipmi_addr             IPMI interface address

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        IPMI User
  -p PASSWORD, --password PASSWORD
                        IPMI User's password
  -d, --discovery       Force discovery
  -t, --debug           Debug script
```

Script sends discovery data at midnight. You can force discovery from command line with -d option.

### Prerequisites

**freeipmi** package should be installed.
```
apt install freeipmi
```
or
```
yum install freeipmi
```