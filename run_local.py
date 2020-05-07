# flasknewsreader/run_local.py
# Version: --
# Author : Jochen Peters

from flask import Flask, redirect, request, render_template
from flask_login import LoginManager, UserMixin, login_user, logout_user
from flasknewsreader import fnr_bp

app = Flask(__name__)
app.register_blueprint(fnr_bp)

# set up flask-login
app.secret_key = 'abc' # CHANGE THIS!
login_manager = LoginManager()
login_manager.init_app(app)
userdb = {} # = {'username': {'password': 'abc'}}

class User(UserMixin):
	pass

@login_manager.user_loader
def user_loader(username):
	if username not in userdb:
		return
	user = User()
	user.id = username
	return user

@login_manager.request_loader
def request_loader(request):
	username = request.form.get('username')
	if username not in userdb:
		return
	user = User()
	user.id = username
	user.is_authenticated = request.form['password'] == userdb[username]['password']
	return user


# routes
@app.route('/login', methods=['POST','GET'])
def news_login():
	if request.method == 'GET':
		return render_template('login.html')
	elif request.method == 'POST':
		username = request.form['username']
		if username in userdb and request.form['password'] == userdb[username]['password']:
			user = User()
			user.id = username
			login_user(user)
			return redirect('/news/settings')
		return 'Login failed'


@app.route('/logout')
def news_logout():
	logout_user()
	return redirect('/news')

@app.route('/')
def baseurl():
	return redirect('/news')


# run
if __name__ == '__main__':
	# remote_access setting is ignored
	app.run(host='127.0.0.1', port=8080, debug=True)

