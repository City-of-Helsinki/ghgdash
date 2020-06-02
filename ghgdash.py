# -*- coding: utf-8 -*-
import dash
import os
import dash_cytoscape as cyto

from flask_session import Session
from flask_babel import Babel

from layout import initialize_app
from common import cache
from common.locale import init_locale


os.environ['DASH_PRUNE_ERRORS'] = 'False'
os.environ['DASH_SILENCE_ROUTES_LOGGING'] = 'False'

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True

server = app.server
with server.app_context():
    server.config.from_object('common.settings')
    server.config['BABEL_TRANSLATION_DIRECTORIES'] = 'locale'

    cache.init_app(server)

    sess = Session()
    sess.init_app(server)

    babel = Babel(default_locale='fi')
    babel.init_app(server)
    init_locale(babel)


cyto.load_extra_layouts()
initialize_app(app)

if __name__ == '__main__':
    # Write the process pid to a file for easier profiling with py-spy
    with open('.ghgdash.pid', 'w') as pid_file:
        pid_file.write(str(os.getpid()))
    app.run_server(debug=True)
