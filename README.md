<div align="center" width="100%">
    <img src="app/templates/images/gptwol.png" width="150" />
</div>

# GPTWOL a simple Wake/Sleep On Lan docker GUI

---
[![Docker Pulls](https://img.shields.io/docker/pulls/misterbabou/gptwol.svg?logo=docker)](https://hub.docker.com/r/misterbabou/gptwol)
[![GitHub Release](https://img.shields.io/github/release/Misterbabou/gptwol.svg?logo=github&logoColor=959DA5)](https://github.com/Misterbabou/gptwol/releases/latest)
[![GitHub last commit](https://img.shields.io/github/last-commit/Misterbabou/gptwol?logo=github&logoColor=959DA5)](https://github.com/Misterbabou/gptwol/commits/main)
[![MIT Licensed](https://img.shields.io/github/license/Misterbabou/gptwol.svg?logo=github&logoColor=959DA5)](https://github.com/Misterbabou/gptwol/blob/main/LICENSE.md)
---

GPTWOL is a simple and lightweight Wake/Sleep on Lan gui made with python to wake up and shutdown your computers on your LAN.

## Screenshot 

| Light Web                         | Dark Web                           |
| --------------------------------- | ---------------------------------- |
| ![](/assets/gptwol-web-light.png) | ![](/assets/gptwol-web-dark.png)   |

| Light Mobile                      | Dark Mobile                        |
| --------------------------------- | ---------------------------------- |
| ![](/assets/gptwol-mob-light.png) | ![](/assets/gptwol-mob-dark.png)   |

## Features 

- Docker Image to deploy
- Run natively with PM2 process manager
- Send Wake On Lan packets to wake up computers (with per-computer network adapter selection)
- Send Sleep On Lan packets to shutdown computers
- Add, Edit, or Delete Computer
- Group computers and filter/sort by Group
- Bulk Add entries from text format (`Name;MAC;IP;StatusCheck;Interface;Group`)
- Computers status check with ping, arp or tcp request (timeout settings available)
- **Uptime monitoring** — per-device timeline graph showing RUNNING/OFF history with adjustable time range
- ARP-SCAN to add computers
- Very low power usage (20 mb RAM)
- Check if IP and MAC provided are valid
- cron job to wake up device
- Check if Cron provided is valid
- Search on computer Name, Group, MAC or IP
- Dark mode
- Authentication (disable by default)

## Special configuration you can change

- Ping Refresh to check Status availability 
- Disable Delete or Add Computers
- Change the port of the Web UI
- Enable authentication (Local auth with only one user or OIDC)

![](/assets/authentication.png)

## Docker Configuration
> [!NOTE]
>
>It's recommended to use docker compose to run this application. [Install documentation](https://docs.docker.com/compose/install/)

> [!CAUTION]
>
>- The app container needs to run in host network mode to send the wakeonlan command on your local network.
>- Make sure that the PORT you are using is free on your host computer
>- Make sure that BIOS settings and remote OS is configure to allow Wake On Lan
>- Don't expose gptwol directly on internet without proper authentication

### 1. Build and Run from Source Code (Local Docker Build)

Clone the repository and build the Docker image locally:

```bash
git clone https://github.com/Misterbabou/gptwol.git
cd gptwol
```

#### Build and run using Docker Compose (Recommended)
```bash
docker compose up -d --build
```

#### Build and run using Docker CLI
```bash
# Build the Docker image
docker build -t gptwol:latest .

# Run the container
docker run -d \
  --name=gptwol \
  --network="host" \
  --restart unless-stopped \
  -e PORT=5000 \
  -e TZ=Europe/Paris \
  -v ./appdata/db:/app/db \
  -v ./appdata/cron:/etc/cron.d \
  gptwol:latest
```

---

### 2. Run Pre-built Image from Docker Hub

#### With docker compose

Create `docker-compose.yml` file:
```yaml
services:
  gptwol:
    container_name: gptwol
    image: misterbabou/gptwol:latest
    network_mode: host
    restart: unless-stopped
    environment:
      - TZ=Europe/Paris #Set your timezone for Cron; default is UTC
      #- PORT=5000 #Free Port on Your host; default is 5000
      #- IP=0.0.0.0 #App listening IPV4 or IPV6 (ex [::]) address; default is 0.0.0.0
      #- LOG_LEVEL=INFO #Can be DEBUG, INFO, WARN or ERROR
      #- ENABLE_LOGIN=false # Enable or disable local login; You would be able to access with USERNAME and PASSWORD; default is false
      #- USERNAME=admin # Set a username; default is admin
      #- PASSWORD=admin # Set a password; default is admin
      #- OIDC_ENABLED=false # Enable OIDC LOGIN; default is false
      #- OIDC_ISSUER=https://auth.exemple.com #  Base URL of the OIDC server - Should not include the `/.well-known/openid-configuration` part and no trailing `/`; default is not set
      #- OIDC_CLIENT_ID=oidcclientid # Your OIDC client ID; default is not set
      #- OIDC_CLIENT_SECRET=oidcclientsecret # Your OIDC Client Secret; default is not set
      #- OIDC_REDIRECT_URI=http(s)://urlofyourgptwol(:port) # Base URL of your GPTWOL instance; default is not set 
      #- SCRIPT_NAME=/my-app # Uncomment this line to run the app under a prefix; default is not set
      #- ENABLE_ADD_DEL=true # Enable or disable ADD computer and Delete computer buttons; default is true
      #- ENABLE_REFRESH=true # Enable or disable automatic status refresh; default is true
      #- REFRESH_INTERVAL=30 # Uncomment to change time between each status check for icmp, arp or tcp, can (in s); default value is 30 seconds
      #- PING_TIMEOUT=300 #Uncomment to change the time to wait for a ping answer in (in ms); default value is 300 milliseconds
      #- ARP_INTERFACE=eth0 #Uncomment this line to set an arp interface manually for scan and test; default is not set
      #- ARP_TIMEOUT=300 #Uncomment to change the time to wait for a arp answer (in ms); default value is 300 milliseconds
      #- TCP_TIMEOUT=1 #Uncomment to change the time to wait for a tcp check (in s);  default value 1 second
      #- DEFAULT_LANG=en # Set default language ('en' or 'pl'); default is en
      #- ENABLE_L2_WOL_PACKET=false # Enable L2 WOL packet instead of L4, default is false
      #- L2_INTERFACE=eth0 # Set the default interface for L2 WOL (set this only if you set ENABLE_L2_WOL_PACKET to true), default is eth0
      #- UPTIME_CHECK_INTERVAL=60 # Interval in seconds between uptime status checks for the uptime graph; default is 60
    volumes:
      - ./appdata/db:/app/db
      - ./appdata/cron:/etc/cron.d
```

Run the application:
```bash
docker compose up -d
```

#### With docker CLI

Run the application using Docker Hub image:
```bash
docker run -d \
  --name=gptwol \
  --network="host" \
  --restart unless-stopped \
  -e PORT=5000 \
  -e TZ=Europe/Paris \
  -v ./appdata/db:/app/db \
  -v ./appdata/cron:/etc/cron.d \
  misterbabou/gptwol:latest
```

---

### 3. Run with PM2 (without Docker)

You can run GPTWOL natively on your system using [PM2](https://pm2.io/), a production-grade Node.js process manager that also works with Python applications.

#### Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)
- **Node.js 16+** and **npm** (for PM2)
- **fping** (for ICMP status checks)
- **arp-scan** (optional, for ARP checks and network scanning)

#### Install system dependencies

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y python3 python3-pip python3-venv fping arp-scan nodejs npm

# RHEL/Fedora
sudo dnf install -y python3 python3-pip fping arp-scan nodejs npm
```

#### Install PM2

```bash
sudo npm install -g pm2
```

#### Clone and set up the application

```bash
git clone https://github.com/Misterbabou/gptwol.git
cd gptwol/app

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

#### Create PM2 ecosystem file

Create `ecosystem.config.js` in the project root (`gptwol/`):

```javascript
module.exports = {
  apps: [{
    name: 'gptwol',
    script: 'venv/bin/python',
    args: 'wol.py',
    cwd: './app',
    interpreter: 'none',
    env: {
      PORT: 5000,
      IP: '0.0.0.0',
      TZ: 'Europe/Paris',
      DB_PATH: './db/computers.db',
      CRON_FILENAME: './cron/gptwol',
      // ENABLE_LOGIN: 'false',
      // USERNAME: 'admin',
      // PASSWORD: 'admin',
      // ENABLE_ADD_DEL: 'true',
      // ENABLE_REFRESH: 'true',
      // REFRESH_INTERVAL: '30',
      // PING_TIMEOUT: '300',
      // ARP_TIMEOUT: '300',
      // TCP_TIMEOUT: '1',
      // DEFAULT_LANG: 'en',
      // UPTIME_CHECK_INTERVAL: '60',
      // LOG_LEVEL: 'INFO',
    }
  }]
};
```

#### Start the application

```bash
# Start with PM2
pm2 start ecosystem.config.js

# Save the process list so PM2 restarts it on reboot
pm2 save

# Set PM2 to start on system boot
pm2 startup
```

#### Common PM2 commands

```bash
pm2 status              # Check app status
pm2 logs gptwol         # View application logs
pm2 restart gptwol      # Restart the application
pm2 stop gptwol         # Stop the application
pm2 delete gptwol       # Remove from PM2 process list
pm2 monit               # Real-time monitoring dashboard
```

> [!NOTE]
>
> When running without Docker, make sure the user running PM2 has the necessary permissions for sending WOL packets (raw sockets) and running `arp-scan`. You may need to run PM2 as root or configure appropriate capabilities:
> ```bash
> sudo setcap cap_net_raw+ep $(which fping)
> sudo setcap cap_net_raw+ep $(which arp-scan)
> ```

## Configure Sleep on Lan

- Check the [Sleep on Lan Github](https://github.com/SR-G/sleep-on-lan) repo to download and configure
- GPTWOL send a reverse MAC wakeonlan packet on port 9 to shutdown your computer (you don't need to configure API)

### Sleep on Lan for a debian based computer

- `sol.json`
```
{
    "Listeners": [
        "UDP:9"
    ],
    "LogLevel": "INFO",
    "Commands": [
        {
            "Operation": "shutdown",
            "Command": "poweroff",
            "Default": true
        }
    ]
}
```

### Sleep on Lan for a windows based computer

- `sol.json`
```
{
    "Listeners": [
        "UDP:9"
    ],
    "LogLevel": "INFO",
    "Commands": [
        {
            "Operation": "shutdown",
            "Command": "shutdown /s /t 0 /f"",
            "Default": true
        }
    ]
}
```
- Configure Windows Defender Firewall by adding a new Inbound Rule (UDP port 9 to allow).
  
## Configure OIDC

- You need to configure your OIDC provider to add new OIDC configuration. You need to enter `http(s)://yourgptwolurl(:port)/auth/oidc/callback` as Redirect URI
- Configure the following ENV variables in docker compose: `OIDC_ENABLED OIDC_ISSUER OIDC_CLIENT_ID OIDC_CLIENT_SECRET OIDC_REDIRECT_URI` (see default docker-compose.yml)


## Roadmap 

:heavy_check_mark: Add ARM version (Added in 1.0.1)

:heavy_check_mark: Add feature to plan automatic Wake on Lan (Cron) (Added in 1.0.3)

:heavy_check_mark: Add Search feature (Added in 1.0.4)

:heavy_check_mark: Remove Cron on Computer deletion (Added in 1.0.4)

:heavy_check_mark: Improve load page performance due to ping timeout. (added in 1.0.5)

:heavy_check_mark: Add a TCP port option to check availability without using ICMP (added in 2.0.1)

:heavy_check_mark: Run app on subpath (added in 2.1.0)

:heavy_check_mark: Make app responsive for smaller screen (added in 2.1.0)

:heavy_check_mark: Add Dark Mode Switch (added in 2.1.3)

:heavy_check_mark: move computers.txt in an other directory not to mount a file but a directory to the docker container (added in 4.0.0)

:heavy_check_mark: Shutdown computers with Sleep on LAN (added in 4.1.0)

:heavy_check_mark: Add optional simple authentication (added in 4.2.0)

:heavy_check_mark: Add ARP SCAN to add you computer of for availability check (added in 5.0.0)

:heavy_check_mark: Add Sort button to sort computer by Name, IP or MAC (added in 5.2.0)

:heavy_check_mark: Migrate computers to a SQLite database (added in 7.0.0)

:heavy_check_mark: OIDC sign in (added in 7.1.0)

:heavy_check_mark: Select ethernet adapter per computer, group filtering, bulk text import, and Polish language support (added in 8.1.0)

:heavy_check_mark: Per-device uptime monitoring with timeline graph and PM2 native deployment support (added in 9.0.0)

## Questions

<details>
<summary>Is there a GUI to configure automatic wakeup and shutdown?</summary>
<br>

Automatic shutdown and wakeup are made in the GUI using cron syntax. As I want to keep the application simple, I will not implement a GUI with a calendar, month an days.
You can check this [link](https://crontab.guru/) to help you build your cron.

</details>
