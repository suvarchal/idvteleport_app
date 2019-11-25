import os
DEBUG = False
SECRET_KEY = os.urandom(24)
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = set(['xidv','zidv']) #,'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

