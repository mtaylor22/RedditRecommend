import praw
import math
import json
from helper import Hw1
from collections import Counter



def get_score(username):
    username = 'madano'
    r = praw.Reddit(user_agent="Reddit Recommend: Subreddit Recommender v3 [User-Grabber]")
    redditor = r.get_redditor(username)
    comment_len = 0
    t = open('tfidf_subs.txt', 'r')
    tf_idf = json.loads(t.read())
    user_words = {}
    df_words = {}
    for comment in redditor.get_comments(limit=100):
        tokens = Hw1.tokenize(str(comment))
        stem = Hw1.stemming(tokens)
        stop = Hw1.stopword(stem)
        for word in stop:
            if word not in user_words.keys():
                user_words[word] = 1
            else:
                user_words[word] += 1
    for key in user_words.keys():
        df_words[key] = 0
        for sub in tf_idf.keys():
            if key in tf_idf[sub].keys():
                df_words[key] += 1

    n = len(tf_idf.keys())
    tfidf = {}
    user_total = 0.0
    for key in user_words.keys():
        tf = 1 + math.log10(user_words[key])
        if df_words[key] != 0 and math.log10(df_words[key]) > 0:
            idf = n/math.log10(df_words[key])
            tfidf[key] = tf * idf
            user_total += math.pow(tfidf[key],2)
        else:
            tfidf[key] = 0
    f = open('recommend.txt', 'w')
    for key in tf_idf.keys():
        sum_df = 0.0
        top = 0.0
        for key2 in tf_idf[key].keys():
            sum_df += math.pow(tf_idf[key][key2],2)
            if key2 in tfidf:
                top += tf_idf[key][key2] * tfidf[key2]
        if sum_df == 0 or user_total == 0:
            score = 0
        else:
            score = top/(math.sqrt(sum_df) * math.sqrt(user_total))
        save_json = {'name': key, 'score': score}
        save_json = json.dump(save_json, f)
        f.write('\n')
    f.close()
    z = open('recommend.txt', 'r') 
    line_num = 1
    list = {}
    while line_num <= 10811:
        temp = json.loads(z.readline())
        list[temp['name']] = temp['score']
        line_num += 1
        
    c = Counter(list)
    x = 1
    for unit in c.most_common():

        print unit
        if x == 10:
            break
        x += 1

    
get_score('madano')