# flasknewsreader/run_local.py
# Version: --
# Author : Jochen Peters

from flask import Flask, redirect
from flasknewsreader import fnr_bp

app = Flask(__name__)
app.register_blueprint(fnr_bp)

@app.route('/')
def baseurl():
	return redirect('/news')

# run
if __name__ == '__main__':
	# remote_access setting is ignored
	app.run(host='127.0.0.1', port=8080, debug=True)

