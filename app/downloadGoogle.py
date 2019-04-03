import requests, zipfile, io
import pandas as pd

def download_file_from_google_drive(id):
    URL = "https://docs.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(URL, params = { 'id' : id }, stream = True)
    token = get_confirm_token(response)

    if token:
        params = { 'id' : id, 'confirm' : token }
        response = session.get(URL, params = params, stream = True)

    return save_response_content(response)    

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None

def save_response_content(response):
    print("* Downloading an unpacking data.")
    df = ''
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip:
        with zip.open('all_pp.csv') as myZip:
            df = pd.read_csv(myZip)
    return df