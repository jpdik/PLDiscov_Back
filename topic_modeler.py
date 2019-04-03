#!/usr/bin/env python
# coding: utf-8

import settings
import os, zipfile, io, requests

import pandas as pd
import numpy as np
from nltk import word_tokenize
import nltk
from string import punctuation
from sklearn.decomposition import NMF
import json
from sklearn.metrics.pairwise import cosine_similarity

# Vetorização
from sklearn.feature_extraction.text import TfidfVectorizer

import downloadGoogle as dg

try:
    stopwords = nltk.corpus.stopwords.words('portuguese')
except LookupError:
    nltk.download('stopwords')
    
numbers = '0123456789'

def download_and_unpack(link_id):
    return dg.download_file_from_google_drive(link_id)

def recarregar_documento():
    df = ''
    get_folder = os.getenv('DATA_CSV', 'data/all_pp.csv')
    if not 'data' in get_folder:
        df = download_and_unpack(get_folder)
    else:
        print("* unpacking data.")
        df = pd.read_csv(get_folder)
    return df.dropna()

df = recarregar_documento()

def trazer_mais_proximas(musica, genre='', quantidade=5):    
    vectorizer = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 1),
        max_features=None,
        binary=False,
        use_idf=True
    )
    if genre:
        data = df[df['genre'] == genre]
        data = data.append({'doc': musica}, ignore_index=True)
    else:
        data = df.append({'doc': musica}, ignore_index=True)
    tfidf_matrix = vectorizer.fit_transform(data['doc'])

    # Calcula todas as similaridades de cada linha
    sim = cosine_similarity(tfidf_matrix, tfidf_matrix[-1])
    
    dfs = pd.DataFrame(sim[:-1])
    
    dfs = dfs.sort_values(by=[0], ascending=False)

    l = dfs.index.values.tolist()[:quantidade]

    return pd.DataFrame([data.iloc[x] for x in l])

def vetorizer(doc):
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(doc)

    return (tfidf_matrix, tfidf_vectorizer)

def topic_modeling(doc, num_topics=10):
    tfidf_matrix, tfidf_vectorizer = vetorizer(doc)
    
    tfidf_feature_names = tfidf_vectorizer.get_feature_names()

    nmf_model = NMF(n_components=num_topics).fit(tfidf_matrix)

    # Matriz de tópicos x documentos (W)
    nmf_W = nmf_model.transform(tfidf_matrix)

    # Matriz de palavras x tópicos (H)
    nmf_H = nmf_model.components_

    return (nmf_H, nmf_W, tfidf_feature_names)


# Função para obter os tópicos
def obtem_topicos(H, W, feature_names, documents, num_top_words, num_top_documents):
    topics = {}
    topics['quantidade'] = len(H)
    topics['topics'] = []
    for topic_idx, topic in enumerate(H):
        doc = {}
        doc['terms'] = [(feature_names[i], round(H[topic_idx][i], 2)) for i in topic.argsort()[:-num_top_words - 1:-1]]     

        # Top documentos relacionados   
        doc['top_docs'] = []
        
        top_doc_indices = np.argsort( W[:,topic_idx] )[::-1][0:num_top_documents]
        for doc_index in top_doc_indices:

            # Id do documento
            id_doc = int(doc_index)            
            
            top_doc = pd.Series.to_json(documents.iloc[doc_index], force_ascii=False)
            
            doc['top_docs'].append(json.loads(top_doc))
            
        topics['topics'].append(doc)
    return topics

def buscar(query, genre='', quantidade=3):
    info = trazer_mais_proximas(query, genre, 200)
    nmf_H, nmf_W, tfidf_feature_names = topic_modeling(info['doc'])       
    return obtem_topicos(nmf_H, nmf_W, tfidf_feature_names, info, 5, quantidade)