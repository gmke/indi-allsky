import time
#from datetime import datetime
#import math
import hashlib


from flask import request
from flask import Blueprint
from flask import jsonify
from flask import abort
from flask import current_app as app

#from flask_login import login_required

from .base_views import BaseView

#from . import db

from .models import IndiAllSkyDbUserTable



bp_api_allsky = Blueprint(
    'wsapi_indi_allsky',
    __name__,
    #url_prefix='/',  # wsgi
    url_prefix='/indi-allsky',  # gunicorn
)


class UploadApiView(BaseView):
    decorators = []


    def dispatch_request(self, entry_id):
        self.authorize()

        # we are now authenticated

        if request.method == 'POST':
            return self.post()
        elif request.method == 'PUT':
            return self.put(entry_id)
        else:
            return jsonify({}), 400


    def post(self):
        #datetime = str(request.json['NEW_DATETIME'])
        pass


    def put(self):
        #media_file = request.files.get('media')
        pass


    def authorize(self):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            app.logger.error('Missing Authoriation header')
            return abort(400)

        try:
            bearer, user_apikey = auth_header.split(' ')
        except ValueError:
            app.logger.error('Malformed API key')
            return abort(400)


        try:
            username, apikey = user_apikey.split(':')
        except ValueError:
            app.logger.error('Malformed API key')
            return abort(400)


        user = IndiAllSkyDbUserTable.query\
            .filter(IndiAllSkyDbUserTable.username == username)\
            .first()


        if not user:
            app.logger.error('Unknown user')
            return abort(400)


        time_floor = int(time.time() / 900) * 900

        hash1 = hashlib.sha256(str(time_floor) + str(user.apikey))
        if apikey != hash1:
            # we do not need to calculate the 2nd hash if the first one works
            hash2 = hashlib.sha256(str(time_floor + 1) + str(user.apikey))
            if apikey != hash2:
                return abort(400)


class ImageUploadApiView(UploadApiView):
    pass


bp_api_allsky.add_url_rule('/upload/image', view_func=ImageUploadApiView.as_view('image_upload_view'), methods=['POST'], defaults={'id': None})
bp_api_allsky.add_url_rule('/upload/image/<int:id>', view_func=ImageUploadApiView.as_view('image_upload_view'), methods=['PUT'])
