import json
import math
from helper import Hw1



x = 0
infilename='sub_info.json'
f=open(infilename,'r')

line_num=1
df = {}
names = {}
while(line_num<=5000):
    current = []
    temp = Hw1.read_line(f.readline())
    names[temp['name']] = {}
    if temp['description'] is not None:
        for word in temp['description']:
            if word.lower() not in df:
                df[word.lower()] = 1.0
                current.append(word.lower())
                names[temp['name']][word.lower()] = 1.0
            else:
                if word.lower() not in current:
                    current.append(word.lower())
                    names[temp['name']][word.lower()] = 1.0
                else:
                    names[temp['name']][word.lower()] += 1.0
                df[word.lower()] = df[word.lower()]+1.0
    line_num+=1
    

    

h = open('data_subreddits.json','r')
temp = Hw1.read_line(h.read())
for key in temp.keys():
    current = []
    try:
        names[key].keys()    
    except KeyError:
        names[key] = {}
    for set in temp[key]['posts']:
        try:
            tokens = Hw1.tokenize(set['title'].encode('utf-8'))
            stem = Hw1.stemming(tokens)
            stop = Hw1.stopword(stem)
            for word in stop:
                if word.lower() not in df and word.lower() not in current:
                    df[word.lower()] = 1.0
                    current.append(word.lower())
                    names[key][word.lower()] = 1.0
                else:
                    if word.lower() not in current:
                        current.append(word.lower())
                        names[key][word.lower()] = 1.0
                    else:
                        names[key][word.lower()] += 1.0
                    df[word.lower()] = df[word.lower()]+1.0
        except TypeError:
            tokens = Hw1.tokenize(set.encode('utf-8'))
            stem = Hw1.stemming(tokens)
            stop = Hw1.stopword(stem)
            for word in stop:
                if word.lower() not in df and word.lower() not in current:
                    df[word.lower()] = 1.0
                    current.append(word.lower())
                    names[key][word.lower()] = 1.0
                else:
                    if word.lower() not in current:
                        current.append(word.lower())
                        names[key][word.lower()] = 1.0
                    else:
                        names[key][word.lower()] += 1.0
                    df[word.lower()] = df[word.lower()]+1.0
n = len(names)





tfidf = {}
for key in names:
    tfidf[key] = {}
    for word in names[key]:
        tf = 1 + math.log10(names[key][word])
        if math.log10(df[word]) > 0:
            idf = n/math.log10(df[word])
            tfidf[key][word] = tf * idf
        else:
            tfidf[key][word] = 0
        
t = open('tfidf_subs.txt', 'w')
json.dump(tfidf, t)


g = open('sub_words.txt', 'w')
i = open('words_count.txt', 'w')
for key in df.keys():
    g.write(key)
    i.write(str(df[key]))
    g.write("\n")
    i.write("\n")
