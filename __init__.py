from flask import Flask
import json
import pymongo
from flask_bcrypt import Bcrypt

with open('../config.json') as config_file:
    config = json.load(config_file)

#initialize Flask app
app = Flask(__name__)
app.secret_key = config['SECRET_KEY']

#connect to MongoDB
client = pymongo.MongoClient(config['MONGO_URI'])
db = client.simple_books_v2_db

bcrypt = Bcrypt()

import routes