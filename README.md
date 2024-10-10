# Readme

## Debian systems
Build debian package:

    ./build-deb.sh

Copy the package to your server and install the package:

    sudo apt install python3-requests python3-psutil
    sudo dpkg -i dist/beacon-agent-0.1.0.deb

Update your configuration, as described below, then restart the service:

    sudo systemctl restart beacon-agent.service

### Uninstall
To uninstall the agent, use the following command:

    sudo dpkg --remove beacon-agent

## Non-Debian systems, using systemd
Build tarball:

    ./build-dist.sh

Copy the package to your server and then extract it:

    tar -xvzf beacon-agent-0.1.0.tar.gz

Move/copy the `beacon-agent` directory to an appropriate place, e.g. `/usr/local/lib`

    sudo mv beacon-agent /usr/local/lib/
    cd /usr/local/lib/beacon-agent

Copy the example config and update it for your system:

    cp example_config.json config.json

Install the systemd service:

    sudo /usr/local/lib/beacon-agent/install_systemd.sh
    sudo journalctl --follow --unit beacon-agent.service

### Upgrade
Copy the package to your server and then extract it:

    tar -xvzf beacon-agent-0.2.0.tar.gz

And use rsync to copy the files, excluding any config file:

    sudo systemctl stop beacon-agent.service
    sudo rsync -avr --exclude='*config.json' beacon-agent/ /usr/local/lib/beacon-agent
    sudo /usr/local/lib/beacon-agent/install_systemd.sh
    sudo systemctl status beacon-agent.service
    sudo journalctl --follow --unit beacon-agent.service

And now remove the temporary files, which were extracted:

    rm -rf beacon-agent*

### Uninstall
To remove the agent, use the following commands:

    sudo systemctl stop beacon-agent.service
    sudo rm /etc/systemd/system/beacon-agent.service
    sudo rm -rf /usr/local/lib/beacon-agent

## Configuration
Configure your `config.json`, by updating the relevant fields:

    {
      "agent": {
        "api_type": "UptimeKuma",
        "api_url": "https://status.example.ch/api/push",
        "api_key": "your_api_key_here",
        "refresh_interval_seconds": 10,
        "notify_delay_minutes": 10,
        "notify_threshold_percent": 90
      },
      "system_metrics": {},
      "smartctl": {
        "enabled": true
      },
      "docker": {
        "enabled": true
      },
      "proxmox": {
        "enabled": true,
        "token_id": "",
        "token_secret": ""
      }
    }

After modifying the file, restart the systemd service:

    sudo systemctl restart beacon-agent.service
