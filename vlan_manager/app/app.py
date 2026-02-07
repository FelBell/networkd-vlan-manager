from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from vlan_manager.core import VlanManager
from vlan_manager.config import Config
import logging

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

vlan_manager = VlanManager()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    vlans = vlan_manager.get_vlans()
    return render_template('dashboard.html', vlans=vlans)

@app.route('/api/vlans', methods=['GET'])
@login_required
def get_vlans():
    return jsonify(vlan_manager.get_vlans())

@app.route('/api/vlans', methods=['POST'])
@login_required
def add_vlan():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    try:
        if not request.is_json:
             data['dhcp'] = 'dhcp' in request.form
             data['forwarding'] = 'forwarding' in request.form
             data['nat'] = 'nat' in request.form
             data['dhcp_gateway'] = request.form.get('dhcp_gateway')
             data['dhcp_dns'] = request.form.get('dhcp_dns')
             data['dhcp_pools'] = request.form.get('dhcp_pools')

        vlan_manager.add_vlan(data)
        flash('VLAN added successfully', 'success')
        if request.is_json:
            return jsonify({"status": "success"}), 201
        return redirect(url_for('dashboard'))
    except ValueError as e:
        flash(str(e), 'error')
        if request.is_json:
            return jsonify({"status": "error", "message": str(e)}), 400
        return redirect(url_for('dashboard'))

@app.route('/api/vlans/delete/<int:vlan_id>', methods=['POST'])
@login_required
def delete_vlan(vlan_id):
    try:
        vlan_manager.delete_vlan(vlan_id)
        flash('VLAN deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting VLAN: {e}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/api/apply', methods=['POST'])
@login_required
def apply_config():
    try:
        vlan_manager.apply_config()
        flash('Configuration applied successfully', 'success')
    except Exception as e:
        flash(f'Failed to apply configuration: {e}', 'error')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
