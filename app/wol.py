from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
import logging
import socket
import struct
import subprocess
import os
import ipaddress
import re
import fcntl

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
  level=getattr(logging, log_level, logging.INFO),
  format='[%(asctime)s] [%(levelname)s] %(message)s',
  datefmt='%Y-%m-%d %H:%M:%S %z'
)
logger = logging.getLogger(__name__)

ping_timeout = os.environ.get('PING_TIMEOUT', 300)
arp_timeout = os.environ.get('ARP_TIMEOUT', 300)
tcp_timeout = os.environ.get('TCP_TIMEOUT', 1)
arp_interface = os.environ.get('ARP_INTERFACE')
l2_wol_packet = os.environ.get('ENABLE_L2_WOL_PACKET', 'false').lower() == 'true'
l2_interface = os.environ.get('L2_INTERFACE', 'eth0')
cron_filename = os.environ.get('CRON_FILENAME', '/etc/cron.d/gptwol')
computer_filename = 'db/computers.txt'

app = Flask(__name__, static_folder='templates')
app.secret_key = os.urandom(24)
enable_login = os.environ.get('ENABLE_LOGIN', 'false').strip().lower() == 'true'

db_path = os.environ.get('DB_PATH', '/app/db/computers.db')
try:
  if os.path.dirname(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
except Exception:
  db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'computers.db')
  os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize OIDC

oidc_enabled = os.environ.get('OIDC_ENABLED', 'false').strip().lower() == 'true'
oidc_issuer = os.environ.get('OIDC_ISSUER', '')
oidc_client_id = os.environ.get('OIDC_CLIENT_ID', '')
oidc_client_secret = os.environ.get('OIDC_CLIENT_SECRET', '')
oidc_redirect_uri = os.environ.get('OIDC_REDIRECT_URI', '').rstrip('/') + '/auth/oidc/callback'
oidc_scopes = os.environ.get('OIDC_SCOPES', 'openid email profile')

oauth = OAuth(app)

if oidc_enabled:
  oauth.register(
    name='oidc',
    server_metadata_url=f'{oidc_issuer}/.well-known/openid-configuration',
    client_id=oidc_client_id,
    client_secret=oidc_client_secret,
    client_kwargs={'scope': oidc_scopes}
  )

def get_or_create_oidc_user(userinfo):
  uid = userinfo.get('sub')
  if not uid:
    raise RuntimeError('OIDC userinfo missing sub')

  # ensure entry in the in-memory store
  if uid not in users:
    users[uid] = {
      'password': None,  # no password for SSO users
      'username': userinfo.get('preferred_username') or userinfo.get('name'),
      'email': userinfo.get('email'),
      'idp': 'oidc'
    }
  return uid

@app.route('/auth/oidc/login')
def login_oidc():
  if not oidc_enabled:
    return redirect(url_for('login'))  # Fallback if disabled

  try:
    # Redirect user to the IdP
    return oauth.oidc.authorize_redirect(redirect_uri=oidc_redirect_uri)
  except Exception as e:
    logger.error(f"OIDC login failed: {e}")
    flash ("SSO LOGIN ERROR", "danger")
    return redirect(url_for('login'))


@app.route('/auth/oidc/callback')
def oidc_callback():
  if not oidc_enabled:
    return redirect(url_for('login'))

  try:
    # Exchange code for tokens
    token = oauth.oidc.authorize_access_token()

    # Parse ID Token (preferred), falling back to UserInfo when needed
    try:
      id_token_claims = oauth.oidc.parse_id_token(token)
      userinfo = id_token_claims
    except Exception:
      userinfo = oauth.oidc.userinfo()

    uid = get_or_create_oidc_user(userinfo)

    # Log the user in via Flask-Login
    user = User(uid)
    login_user(user)

    display_name = users[uid].get("email") or users[uid].get("username") or uid

    user_ip = request.remote_addr
    logger.info(f"Success OIDC login for user '{display_name}' from IP: {user_ip}")
    flash (f"Connected as: {display_name}", "success")
    return redirect(url_for('wol_form'))

  except Exception as e:
    logger.error(f"OIDC callback failed: {e}")
    flash ("SSO CALLBACK ERROR", "danger")
    return redirect(url_for('login'))

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to this route if not logged in

auth_enabled = (enable_login or oidc_enabled)
app.config['LOGIN_DISABLED'] = not auth_enabled

# In-memory user store (for simplicity)
username = os.environ.get('USERNAME', 'admin').strip('"')
password = os.environ.get('PASSWORD', 'admin').strip('"')
users = {username: {'password': password}}

# User model
class User(UserMixin):
  def __init__(self, id):
    self.id = id

@login_manager.user_loader
def load_user(user_id):
  return User(user_id) if user_id in users else None

@app.route('/login', methods=['GET', 'POST'])
def login():
  if not enable_login and not oidc_enabled:
    return redirect(url_for('wol_form'))  # Skip login
  if request.method == 'POST':
    user_ip = request.remote_addr
    username = request.form['username']
    password = request.form['password']
    if username in users and users[username]['password'] == password:
      user = User(username)
      login_user(user)
      logger.info(f"Success local login for user '{username}' from IP: {user_ip}")
      flash (f"Connected as: {username}", "success")
      return redirect(url_for('wol_form'))

    logger.warning(f"Failed local login attempt for user '{username}' from IP: {user_ip}")
    flash ("Invalid Credentials", "danger")
    return redirect(url_for('login'))
  return render_template('login_form.html', os=os)

@app.route('/logout')
@login_required
def logout():
  logout_user()
  session.clear()
  return redirect(url_for('login'))

def generate_modal_html(messages, title):
  message_content = '<br>'.join(messages)
  return render_template('generate_modal.html', title=title, message_content=message_content)

class Computer(db.Model):
  name = db.Column(db.String(64), nullable=False)
  mac_address = db.Column(db.String(17), unique=True, primary_key=True, nullable=False)
  ip_address = db.Column(db.String(45), nullable=False)
  test_type = db.Column(db.String(10), nullable=False)
  interface = db.Column(db.String(64), nullable=False)
  group_name = db.Column(db.String(64), nullable=True, default='')

def migrate_db_schema():
  with db.engine.connect() as conn:
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if 'computer' in inspector.get_table_names():
      columns = [col['name'] for col in inspector.get_columns('computer')]
      if 'interface' not in columns:
        conn.execute(text("ALTER TABLE computer ADD COLUMN interface VARCHAR(64) NOT NULL DEFAULT 'eth0'"))
        conn.commit()
      if 'group_name' not in columns:
        conn.execute(text("ALTER TABLE computer ADD COLUMN group_name VARCHAR(64) DEFAULT ''"))
        conn.commit()

def migrate_txt_to_db():
  if not os.path.exists(computer_filename):
    return

  with open(computer_filename) as f:
    for line in f:
      fields = line.strip().split(',')
      if len(fields) < 3:
        continue
      name, mac, ip = fields[0], fields[1], fields[2]
      test_type = fields[3] if len(fields) > 3 else 'icmp'
      interface = fields[4] if len(fields) > 4 else 'eth0'
      group_name = fields[5] if len(fields) > 5 else ''

      if not Computer.query.filter_by(mac_address=mac).first():
        c = Computer(name=name, mac_address=mac, ip_address=ip, test_type=test_type, interface=interface, group_name=group_name)
        db.session.add(c)

  db.session.commit()
  os.rename(computer_filename, f"{computer_filename}.old")

def load_computers():
  global cron_filename
  computers = []

  for c in Computer.query.all():
    computers.append({
      'name': c.name,
      'mac_address': c.mac_address,
      'ip_address': c.ip_address,
      'test_type': c.test_type,
      'interface': c.interface,
      'group_name': c.group_name or ''
    })

  # Cron loading
  if not os.path.exists(cron_filename):
    try:
      if os.path.dirname(cron_filename):
        os.makedirs(os.path.dirname(cron_filename), exist_ok=True)
      open(cron_filename, 'w').close()
    except Exception:
      cron_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cron', 'gptwol')
      os.makedirs(os.path.dirname(cron_filename), exist_ok=True)
      open(cron_filename, 'w').close()

  with open(cron_filename) as f:
    for line in f:
      if not line.startswith('#'):
        fields = line.strip().split()
        schedule = ' '.join(fields[:5])
        user = fields[5]
        command = ' '.join(fields[6:])
        mac_address = command.split()[-1]
        reversed_mac_address = ':'.join(reversed(mac_address.split(':')))

        # Find and add cron info to matching computer
        for computer in computers:
          if computer['mac_address'] == mac_address:
            computer['cron_wol_schedule'] = schedule
          if computer['mac_address'] == reversed_mac_address:
            computer['cron_sol_schedule'] = schedule

  return computers

def get_interface_mac(interface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        info = fcntl.ioctl(
            s.fileno(),
            0x8927,  # SIOCGIFHWADDR
            struct.pack('256s', interface.encode('utf-8')[:15])
        )
        return info[18:24]  # MAC address bytes
    finally:
        s.close()

def send_l2_wol_packet(mac_address, interface):
    # Clean and convert target MAC address to bytes
    mac_clean = mac_address.replace(':', '').replace('-', '')
    mac_bytes = bytes.fromhex(mac_clean)

    # Build the magic packet
    magic_packet = b'\xff' * 6 + mac_bytes * 16

    # Destination: broadcast, Source: real MAC from interface
    dst_mac = b'\xff\xff\xff\xff\xff\xff'
    src_mac = get_interface_mac(interface)
    eth_type = b'\x08\x42'  # Wake-on-LAN EtherType

    # Construct Ethernet frame
    ether_frame = dst_mac + src_mac + eth_type + magic_packet

    # Send via raw socket
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
    try:
        s.bind((interface, 0))
        s.send(ether_frame)
    finally:
        s.close()

def send_wol_packet(mac_address, interface=None):
  # Convert the MAC address to a packed binary string
  packed_mac = struct.pack('!6B', *[int(x, 16) for x in mac_address.split(':')])

  # Create a socket and send the WOL packet
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
  if interface:
    try:
      s.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_BINDTODEVICE', 25), interface.encode('utf-8'))
    except Exception as e:
      logger.error(f"Failed to bind WOL socket to interface {interface}: {e}")
  try:
    s.sendto(b'\xff' * 6 + packed_mac * 16, ('<broadcast>', 9))
  finally:
    s.close()

def is_computer_awake(ip_address, port):
  if not port or port.lower() == 'icmp':
    return is_computer_awake_icmp(ip_address)
  if port.lower() == 'arp':
    return is_computer_awake_arp(ip_address)
  else:
    port_int = int(port)
    return is_computer_awake_tcp(ip_address, port_int)

def is_computer_awake_icmp(ip_address, timeout=ping_timeout):
  # Use the fping command with a timeout to check if the computer is awake
  try:
    result = subprocess.run(['fping', '-t', str(timeout), '-c', '1', ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0
  except FileNotFoundError:
    # Fallback to standard ping if fping is not installed
    try:
      result = subprocess.run(['ping', '-c', '1', '-W', '1', ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      return result.returncode == 0
    except Exception:
      return False

def is_computer_awake_arp(ip_address, timeout=arp_timeout):
  # Use the arp-scan command to check if the computer is awake
  command = ['arp-scan', '-qx', '-t', str(timeout), ip_address]
  if arp_interface:
    command += ['-I', arp_interface]

  try:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    # Check if there is any output in stdout
    return bool(result.stdout.strip())
  except FileNotFoundError:
    return False

def is_computer_awake_tcp(ip_address, port, timeout=tcp_timeout):
  # Use nc (netcat) to check if the TCP port is open
  result = subprocess.run(['nc', '-z', '-w', str(timeout), ip_address, str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  return result.returncode == 0

def check_mac_exist(mac_address):
  return db.session.query(Computer.mac_address).filter_by(mac_address=mac_address).first() is not None

def check_invalid_name(name):
  return ',' in name

def check_invalid_ip(ip):
  try:
    ipaddress.ip_address(ip)
    return False # Valid IP
  except ValueError:
    return True # Invalid IP

def check_invalid_mac(mac):
  # Regular expression for validating a MAC address
  mac_pattern = r'^([0-9a-fA-F]{2}:){5}([0-9a-fA-F]{2})$'
  # Check if the MAC address matches the pattern
  if re.match(mac_pattern, mac):
    return False  # Valid MAC address
  else:
    return True   # Invalid Mac address

def check_invalid_test_type(test_type):
  # Check if test_type is "icmp" or a valid port number
  if test_type == "icmp" or test_type == "arp":
    return False  # "icmp" is valid
  return not (test_type.isdigit() and 0 <= int(test_type) <= 65535)

def check_invalid_interface(interface):
  return not interface or not interface.strip() or ',' in interface

def check_invalid_group(group_name):
  return ',' in group_name

def check_invalid_cron(cron):
  # Regular expressions for each field
  patterns = [
    r'^(\*|[1-5]?[0-9](-[1-5]?[0-9])?)(\/[1-9][0-9]*)?(,(\*|[1-5]?[0-9](-[1-5]?[0-9])?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|(1?[0-9]|2[0-3])(-(1?[0-9]|2[0-3]))?)(\/[1-9][0-9]*)?(,(\*|(1?[0-9]|2[0-3])(-(1?[0-9]|2[0-3]))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|([1-9]|[1-2][0-9]?|3[0-1])(-([1-9]|[1-2][0-9]?|3[0-1]))?)(\/[1-9][0-9]*)?(,(\*|([1-9]|[1-2][0-9]?|3[0-1])(-([1-9]|[1-2][0-9]?|3[0-1]))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|([1-9]|1[0-2]?)(-([1-9]|1[0-2]?))?)(\/[1-9][0-9]*)?(,(\*|([1-9]|1[0-2]?)(-([1-9]|1[0-2]?))?)(\/[1-9][0-9]*)?)*$',
    r'^(\*|[0-6](-[0-6])?)(\/[1-9][0-9]*)?(,(\*|[0-6](-[0-6])?)(\/[1-9][0-9]*)?)*$'
  ]

  # Split the cron expression into its components
  parts = cron.split()
  if len(parts) != 5:
    return True  # Invalid if not exactly 5 parts

  # Validate each part using the corresponding regex
  return any(not re.match(pattern, part) for pattern, part in zip(patterns, parts))

def delete_cron_entry(request_mac_address):
  with open(cron_filename, 'r') as f:
    lines = f.readlines()

  # Look for the line with the specified MAC address and remove it
  new_lines = []
  deleted = False
  for line in lines:
    if line.startswith('#'):
      new_lines.append(line)
    else:
      fields = line.strip().split()
      schedule = ' '.join(fields[:5])
      user = fields[5]
      command = ' '.join(fields[6:])
      mac_address = command.split()[-1]
      if mac_address == request_mac_address:
        deleted = True
      else:
        new_lines.append(line)

    # If a line was deleted, write the new contents to the file
  if deleted:
    with open(cron_filename, 'w') as f:
      f.writelines(new_lines)
  return redirect(url_for('wol_form'))

@app.route('/')
@login_required
def wol_form():
  computers = load_computers()
  groups = sorted(list({c['group_name'] for c in computers if c.get('group_name')}))
  return render_template('wol_form.html', computers=computers, groups=groups, is_computer_awake=lambda *_: "asleep", os=os)

@app.route('/delete_computer', methods=['POST'])
@login_required
def delete_computer():
  mac_address = request.form['mac_address']

  # Delete the wol cron schedule for the mac_address
  delete_cron_entry(mac_address)
  # Delete the sol cron schedule for the reversed_mac_address
  reversed_mac_address = ':'.join(reversed(mac_address.split(':')))
  delete_cron_entry(reversed_mac_address)

  Computer.query.filter_by(mac_address=mac_address).delete()
  db.session.commit()

  return redirect(url_for('wol_form'))

@app.route('/add_computer', methods=['POST'])
@login_required
def add_computer():
  name = request.form['name'].strip()
  mac_address = request.form['mac_address'].strip()
  ip_address = request.form['ip_address'].strip()
  test_type = request.form['test_type'].strip()
  interface = request.form['interface'].strip()
  group_name = request.form.get('group_name', '').strip()

  messages = []
  # Check Entries
  if check_mac_exist(mac_address):
    messages.append(f'Computer mac: {mac_address} already exists.')
  if check_invalid_name(name):
    messages.append(f'NAME: {name} is invalid. Character , is invalid')
  if check_invalid_ip(ip_address):
    messages.append(f'IP: {ip_address} is invalid.')
  if check_invalid_mac(mac_address):
    messages.append(f'MAC: {mac_address} is invalid.')
  if check_invalid_test_type(test_type):
    messages.append(f'Status check: {test_type} is invalid. Enter "icmp", "arp" or a valid TCP port number.')
  if check_invalid_interface(interface):
    messages.append(f'Ethernet adapter: {interface} is invalid or missing.')
  if check_invalid_group(group_name):
    messages.append(f'Group: {group_name} is invalid. Character , is invalid')
  if messages:
    return generate_modal_html(messages, 'Add Computer Error')

  new_computer = Computer(name=name, mac_address=mac_address, ip_address=ip_address, test_type=test_type, interface=interface, group_name=group_name)
  db.session.add(new_computer)
  db.session.commit()

  return redirect(url_for('wol_form'))

@app.route('/edit_computer', methods=['POST'])
@login_required
def edit_computer():
  name = request.form['name'].strip()
  mac_address = request.form['mac_address'].strip()
  ip_address = request.form['ip_address'].strip()
  test_type = request.form['test_type'].strip()
  interface = request.form['interface'].strip()
  group_name = request.form.get('group_name', '').strip()

  # Find the computer being edited
  computer_to_edit = Computer.query.filter_by(mac_address=mac_address).first()

  messages = []
  if computer_to_edit is None:
    messages.append(f'Computer with MAC address: {mac_address} not found.')
  if check_invalid_name(name):
    messages.append(f'NAME: {name} is invalid. Character , is invalid')
  if check_invalid_ip(ip_address):
    messages.append(f'IP: {ip_address} is invalid.')
  if check_invalid_test_type(test_type):
    messages.append(f'Status check: {test_type} is invalid. Enter "icmp", "arp" or a valid TCP port number.')
  if check_invalid_interface(interface):
    messages.append(f'Ethernet adapter: {interface} is invalid or missing.')
  if check_invalid_group(group_name):
    messages.append(f'Group: {group_name} is invalid. Character , is invalid')
  if messages:
    return generate_modal_html(messages, 'Edit Computer Error')

  if (computer_to_edit.name == name and computer_to_edit.ip_address == ip_address and computer_to_edit.test_type == test_type and computer_to_edit.interface == interface and (computer_to_edit.group_name or '') == group_name):
    messages.append(f'No change was made.')
    return generate_modal_html(messages, 'Edit Computer Info')

  computer_to_edit.name = name
  computer_to_edit.ip_address = ip_address
  computer_to_edit.test_type = test_type
  computer_to_edit.interface = interface
  computer_to_edit.group_name = group_name
  db.session.commit()

  return redirect(url_for('wol_form'))

@app.route('/bulk_add', methods=['GET', 'POST'])
@login_required
def bulk_add():
  if os.environ.get('ENABLE_ADD_DEL') == 'false':
    flash('Adding computers is disabled.', 'danger')
    return redirect(url_for('wol_form'))

  if request.method == 'POST':
    bulk_text = request.form.get('bulk_text', '')
    lines = bulk_text.splitlines()

    added_count = 0
    errors = []
    macs_in_batch = set()

    for idx, line_raw in enumerate(lines, start=1):
      line = line_raw.strip()
      if not line or line.startswith('#'):
        continue

      fields = [f.strip() for f in line.split(';')]
      if len(fields) < 3:
        errors.append(f"Line {idx}: Invalid format. At least 3 parameters (Name;MAC;IP) required")
        continue

      name = fields[0]
      mac_address = fields[1]
      ip_address = fields[2]
      test_type = fields[3] if len(fields) > 3 and fields[3] else 'icmp'
      interface = fields[4] if len(fields) > 4 and fields[4] else 'eth0'
      group_name = fields[5] if len(fields) > 5 else ''

      line_errors = []
      if mac_address in macs_in_batch or check_mac_exist(mac_address):
        line_errors.append(f"MAC '{mac_address}' already exists")
      if check_invalid_name(name):
        line_errors.append(f"Name '{name}' is invalid")
      if check_invalid_ip(ip_address):
        line_errors.append(f"IP '{ip_address}' is invalid")
      if check_invalid_mac(mac_address):
        line_errors.append(f"MAC '{mac_address}' is invalid")
      if check_invalid_test_type(test_type):
        line_errors.append(f"Status check '{test_type}' is invalid")
      if check_invalid_interface(interface):
        line_errors.append(f"Interface '{interface}' is invalid")
      if check_invalid_group(group_name):
        line_errors.append(f"Group '{group_name}' is invalid")

      if line_errors:
        errors.append(f"Line {idx} ({name}): " + ", ".join(line_errors))
      else:
        macs_in_batch.add(mac_address)
        new_computer = Computer(
          name=name,
          mac_address=mac_address,
          ip_address=ip_address,
          test_type=test_type,
          interface=interface,
          group_name=group_name
        )
        db.session.add(new_computer)
        added_count += 1

    if added_count > 0:
      db.session.commit()

    if errors:
      messages = []
      if added_count > 0:
        messages.append(f"Successfully added {added_count} computer(s).")
      messages.append("<b>The following line(s) failed:</b>")
      messages.extend(errors)
      return generate_modal_html(messages, 'Bulk Add Results')

    flash(f"Successfully added {added_count} computer(s)!", "success")
    return redirect(url_for('wol_form'))

  computers = load_computers()
  groups = sorted(list({c['group_name'] for c in computers if c.get('group_name')}))
  return render_template('bulk_add.html', groups=groups, os=os)

def add_cron(mac_address, request_cron):
  messages = []
  # Check Entries
  if check_invalid_cron(request_cron):
    messages.append('Invalid cron expression!')
    messages.append('See : <a href="https://crontab.guru/" target="_blank" rel="noopener noreferrer">Crontab maker</a>')
    return generate_modal_html(messages, 'Add Cron Error')

  cron_command = f"{request_cron} root /usr/local/bin/wakeonlan {mac_address}"
  with open(cron_filename, "a") as f:
    f.write(f"{cron_command}\n")
  return redirect(url_for('wol_form'))

@app.route('/add_wol_cron', methods=['POST'])
@login_required
def add_wol_cron():
  request_mac_address = request.form['mac_address']
  request_cron = request.form['cron_request']
  return add_cron(request_mac_address, request_cron)

@app.route('/add_sol_cron', methods=['POST'])
@login_required
def add_sol_cron():
  request_mac_address = request.form['mac_address']
  reversed_mac_address = ':'.join(reversed(request_mac_address.split(':')))
  request_cron = request.form['cron_request']
  return add_cron(reversed_mac_address, request_cron)

@app.route('/delete_wol_cron', methods=['POST'])
@login_required
def delete_wol_cron():
  request_mac_address = request.form['mac_address']
  delete_cron_entry(request_mac_address)
  return redirect(url_for('wol_form'))

@app.route('/delete_sol_cron', methods=['POST'])
@login_required
def delete_sol_cron():
  request_mac_address = request.form['mac_address']
  reversed_mac_address = ':'.join(reversed(request_mac_address.split(':')))
  delete_cron_entry(reversed_mac_address)
  return redirect(url_for('wol_form'))

@app.route('/check_status')
@login_required
def check_status():
  ip_address = request.args.get('ip_address')
  test_type = request.args.get('test_type')
  if is_computer_awake(ip_address,test_type):
    return 'awake'
  else:
    return 'asleep'

@app.route('/wol_or_sol_send', methods=['POST'])
@login_required
def wol_or_sol_send():
  mac_address = request.form['mac_address']
  computers = load_computers()

  computer = next(c for c in computers if c['mac_address'] == mac_address)
  ip_address = computer['ip_address']
  test_type = computer['test_type']
  interface = computer['interface']

  messages = []
  if is_computer_awake(ip_address, test_type):
    reversed_mac_address = ':'.join(reversed(mac_address.split(':')))
    send_wol_packet(reversed_mac_address, interface=interface)
    title = "Shutdown"
    messages.append(f"Sleep On Lan Magic Packet Sent to {computer['name']}!")
    messages.append('See : <a href="https://github.com/Misterbabou/gptwol#configure-sleep-on-lan" target="_blank" rel="noopener noreferrer">how to configure Sleep on LAN</a>')
  else:
    if l2_wol_packet:
      messages.append(f"Wake On Lan Mode: L2 Packet")
      send_l2_wol_packet(mac_address, interface)
    else:
      messages.append(f"Wake On Lan Mode: L4 Packet")
      send_wol_packet(mac_address, interface=interface)
    title = "Wakeup"
    messages.append(f"Wake On Lan Magic Packet Sent to {computer['name']}!")

  return generate_modal_html(messages, title)

@app.route('/arp_scan', methods=['GET'])
@login_required
def arp_scan():
  try:
    # Load the list of active computers
    computers = load_computers()
    active_mac_addresses = {computer['mac_address'] for computer in computers}

    command = ['arp-scan', '-lqx', '-t', str(arp_timeout)]
    if arp_interface:
      command += ['-I', arp_interface]

    result = subprocess.check_output(command, universal_newlines=True)
    lines = result.strip().split('\n')

    devices = []
    for line in lines:
      parts = line.split()
      if len(parts) >= 2:
        ip_address = parts[0]
        mac_address = parts[1]
        # Exclude MAC addresses that are already in the active computers list
        if mac_address not in active_mac_addresses:
          devices.append({'ip': ip_address, 'mac': mac_address})

    if not devices:
      return jsonify({'message': 'No new devices found.'})
    return jsonify(devices)

  except Exception as e:
    return jsonify({'message': str(e)}), 500

with app.app_context():
  db.create_all()
  migrate_db_schema()
  migrate_txt_to_db()

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  ip = os.environ.get('IP', '0.0.0.0')
  app.run(host=ip, port=port)
