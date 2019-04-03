#coding: utf-8

import os
if os.path.isfile('.env'):
    import settings

import paypalrestsdk
from flask import Flask, request, redirect, g, render_template, jsonify
from flask_jwt_extended import (
    JWTManager, jwt_required, jwt_optional, create_access_token,
    get_jwt_identity, get_jwt_claims
)

from datetime import datetime, timedelta

from flask_cors import CORS
import spotify
import json
import topic_modeler as tm

# Banco de Dados
import pymongo
from pymongo import MongoClient, ReturnDocument

cliente = MongoClient(os.getenv('DATABASE_URI', 'null'))
banco = cliente['pldiscov']

app = Flask(__name__)
CORS(app, allow_headers=['Origin', 'X-Requested-With',
                         'Content-Type', 'Accept', 'Authorization'])

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'null')
jwt = JWTManager(app)


def getAmmount(typeAcc):
    if typeAcc == 1:
        return 4
    elif typeAcc == 2:
        return 10
    elif typeAcc == 3:
        return 30
    else:
        return 2


def checkAmmountSearchs(usuario):
    if 'todaySearch' in usuario and usuario['todaySearch'] < datetime.now():
        usuario['searchedToday'] = 0

    if usuario['searchedToday'] == 0:
        usuario['todaySearch'] = datetime.now() + timedelta(days=1)

    if usuario['type'] == 0 and usuario['searchedToday'] < 20:
        return True
    elif usuario['type'] == 1 and usuario['searchedToday'] < 40:
        return True
    elif usuario['type'] == 2 and usuario['searchedToday'] < 100:
        return True
    elif usuario['type'] == 3 and usuario['searchedToday'] < 1000:
        return True
    return False


def addAmmountSearch(usuario):
    usuarios = banco['usuarios']

    usuario['searchedToday'] += 1
    usuarios.update_one({'email': usuario['email']}, {"$set": usuario})

    return usuario['searchedToday']


def validPremium(usuario):
    usuarios = banco['usuarios']

    if usuario['type'] > 0:
        if usuario['expiration_buy'] < datetime.now():
            usuario['type'] = 0
            usuarios.update_one({'email': usuario['email']}, {"$set": usuario})

    return usuario


@jwt.user_claims_loader
def add_claims_to_access_token(identity):
    usuarios = banco['usuarios']

    usuario = usuarios.find_one({"email": identity})
    if usuario != None:
        return {'user': usuario['user'], 'email': usuario['email'], "type": usuario['type']}
    return {'user': 'Guest'}


@app.route('/login', methods=['POST'])
def login():
    usuarios = banco['usuarios']

    if not request.is_json:
        return jsonify({"msg": "Only JSON"}), 400

    email = request.json.get('email', None)
    password = request.json.get('password', None)

    usuario = usuarios.find_one({"email": email, "password": password})

    if usuario != None:
        usuario = validPremium(usuario)

        del usuario['_id']
        del usuario['password']

        expires = timedelta(days=30)
        # Identity can be any data that is json serializable
        usuario['token'] = create_access_token(
            identity=email, expires_delta=expires)

        return jsonify(usuario), 200
    return jsonify({"msg": "Email ou senha não confere."}), 400


@app.route('/signup', methods=['POST'])
def register():
    usuarios = banco['usuarios']

    if not request.is_json:
        return jsonify({"msg": "Only JSON"}), 400

    email = request.json.get('email', None)
    user = request.json.get('name', None)
    password = request.json.get('password', None)
    confirm_password = request.json.get('confirm_password', None)

    if user and email and password:
        usuario = usuarios.find_one({"email": email})

        if usuario != None:
            return jsonify({'msg': 'Usuário já cadastrado.'}), 400

        if password != confirm_password:
            return jsonify({'msg': 'Senha não bate com a confirmação'}), 400

        usuario = {"user": user, "email": email,
                   "password": password, "type": 0, "searchedToday": 0}
        usuarios.insert_one(usuario)

        expires = timedelta(days=30)
        del usuario['_id']
        del usuario['password']

        usuario['token'] = create_access_token(
            identity=email, expires_delta=expires)
        return jsonify(usuario), 200
    return jsonify({'msg': 'Você precisa informar o usuário, e-mail e senha.'}), 400


@app.route('/checkPurchase', methods=['POST'])
@jwt_optional
def checkPurchase():
    usuarios = banco['usuarios']

    data = request.json['data']

    current_user = get_jwt_claims()

    if current_user:
        if not 'paid' in data:
            return jsonify({"msg": "A transação não foi realizada."}), 400
        if 'paymentID' in data:
            payment = paypalrestsdk.Payment.find(data['paymentID'])
            typeAcc = 0
            value = payment['transactions'][0]['amount']['total']

            if value == "20.00":
                typeAcc = 3
            elif value == "10.00":
                typeAcc = 2
            elif value == "5.00":
                typeAcc = 1

            usuario = usuarios.find_one_and_update({"email": current_user['email']}, {"$set": {
                                                   "type": typeAcc, "expiration_buy": datetime.now() + timedelta(days=30)}}, return_document=ReturnDocument.AFTER)

            if usuario != None:
                del usuario['_id']
                del usuario['password']

                expires = timedelta(days=30)

                usuario['token'] = create_access_token(
                    identity=usuario['email'], expires_delta=expires)
                return jsonify(usuario), 200
            return jsonify({"msg": "Email ou senha não confere."}), 400
        else:
            return jsonify({'msg': 'A transação não foi realizada.'}), 400
    else:
        return jsonify({'msg': 'Você Precisa estar logado!'}), 400


@app.route('/validateToken', methods=['POST'])
@jwt_optional
def validateToken():
    current_user = get_jwt_claims()

    if current_user:
        return jsonify(valid=True), 200
    else:
        return jsonify(valid=False), 200


@app.route("/")
@jwt_optional
def index():
    current_user = get_jwt_claims()

    musics = []
    query = request.args.get('query', '')
    genre = request.args.get('genre', '')
    results = []

    if not current_user:
        return jsonify({'msg': 'Logue para realizar buscas.'}), 400

    usuarios = banco['usuarios']

    usuario = usuarios.find_one({"email": current_user['email']})

    if not usuario:
        return jsonify({'msg': 'Usuario não encontrado.'}), 400

    usuario = validPremium(usuario)

    if usuario['type'] == 0 and genre != '':
        return jsonify({'msg': 'Você precisa ser premium para poder escolher genero.'}), 400

    if query:
        if checkAmmountSearchs(usuario):

            results = tm.buscar(query, genre, getAmmount(current_user['type']))
            for topics in results['topics']:
                [musics.append(x) for x in [spotify.search_music(
                    result['title_music'], result['artist'], result['url'], result['genre']) for result in topics['top_docs']]]

            for i, value in enumerate(musics):
                musics[i]['_id'] = i

            searchs = addAmmountSearch(usuario)
            return json.dumps({"musics": musics, "number_searchs": searchs})
        else:
            return jsonify({'msg': 'Você excedeu o limite de buscas de hoje.'}), 400
    return jsonify({'msg': 'Você precisa informar uma busca.'}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
