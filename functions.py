import json
import re
from urllib.request import urlopen
import requests
from bs4 import BeautifulSoup
from multiprocessing import Pool
from functools import partial
import pandas as pd
import numpy as np
from eunjeon import Mecab
import gensim
from sklearn.metrics.pairwise import cosine_similarity
mecab = Mecab()
word2vec_model = gensim.models.Word2Vec.load('word2vec_by_mecab.model')
containers = ['NNG', 'NNP', 'NNB', 'NNBC', 'NR', 'NP', 'VV', 'VA', 'VX', 'VCP', 'VCN', 'MM']
stop_words = ['JKC', 'JKG', 'JKO', 'JKB', 'JKV', 'JKQ', 'JX', 'JC']
useless_NNG = ['만족','구입','구매','생각','때','주문','정도','느낌','맘','마음','상품','제품','물건']
con = pd.read_csv("word_vector.csv", usecols=['0', 'total_value'])
word_index = set(con['0'].to_list())
con = np.array(con)
weights = np.load('weights.npy', allow_pickle=True)
hangul = re.compile('[^0-9a-zA-Z가-힣\s]')
sss_compile = re.compile('[^0-9a-zA-Z가-힣\s]')
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36'}

def sigmoid(x):
    x = np.array(x).flatten()
    return 1/(1+np.exp(-x))

def positive_or_negative(arr):
    return 1 / (1 + np.exp(
        -1 * (np.dot([0 if h < 0 else h for h in np.dot(arr, weights[0]) + weights[1]], weights[2]) + weights[3])))

def DNN_func(sentence):
    after_preprocess = re.sub(r" {2,}", " ", hangul.sub(' ', sentence))
    after_preprocess = after_preprocess.strip()
    tmp = [text[0] for text in mecab.pos(after_preprocess) if
           text[1][0] != 'E' and text[1][0] != 'S' and (text[1] == 'XR' or text[1][0] != 'X') and text[1][0] != 'J' and text[
               1] != 'UNKNOWN' and text[0] != '.' and text[0] !='옷']
    value = [float(con[con[:, 0] == word, 1]) if word in word_index else 0 for word in tmp]
    if len(value) >= 20:
        value = value[:20]
    else:
        value = np.pad(value, (0, 20 - len(value)), 'constant')

    consider_relu = [0 if h < 0 else 1 for h in np.dot(value, weights[0]) + weights[1]]
    arr = [*map(np.sum, [[h * weights[2][index] + weights[3] / (20 * 10) for index, h in enumerate(
        [0 if consider_relu[index] == 0 else value[i] * weights[0][i][index] + weights[1][index] / 20 for index in
         range(10)])] for i in range(20)])]

    before_text = sentence.split(' ')
    arr_num, values = 0, []
    for before_mecab in before_text:
        value_tmp = 0
        for k in range(len(mecab.morphs(before_mecab))):
            if arr_num + k >= 20: break
            value_tmp = value_tmp + arr[arr_num + k]
        else:
            k=0
        arr_num = arr_num + k + 1
        values.append(round(value_tmp, 3))
    if len(values) < 3:
        if max(values) > min(values)*-1:
            tmp = [max(values) for i in range(len(values))]
        else:
            tmp = [min(values) for i in range(len(values))]
        return before_text, [*map(lambda x: round(x, 2), tmp)], positive_or_negative(value), values

    tmp = []
    for i in range(len(values)):
        if i ==0:
            big = max(values[i],values[i + 1],values[i + 2])
            small = min(values[i],values[i + 1],values[i + 2])
            if big >= small*-1:
                tmp.append(big)
            else:
                tmp.append(small)
        elif i== len(values)-1:
            big = max(values[i],values[i - 1],values[i - 2])
            small = min(values[i],values[i - 1],values[i - 2])
            if big >= small*-1:
                tmp.append(big)
            else:
                tmp.append(small)
        else:
            big = max(values[i],values[i - 1],values[i +1])
            small = min(values[i],values[i - 1],values[i +1])
            if big >= small*-1:
                tmp.append(big)
            else:
                tmp.append(small)


    return before_text, [*map(lambda x: round(x, 2), tmp)], positive_or_negative(value), values

def make_score(x):
    if x < -2.16:
        return -2
    elif x >= 1.84:
        return 2
    else:
        return x+0.16
def make_score2(x):
    return x/4 +0.5

def Crawling_11st(product_num, pageNo):
    try:
        url = 'https://m.11st.co.kr/products/v1/app/products/{}/reviews/list?pageNo={}&sortType=01&pntVals=&rtype=&themeNm='.format(
            product_num, pageNo)
        response = urlopen(url)
        json_data = json.load(response)['review']['list']
        temp = []
        for rev in json_data:
            if rev['subject']:
                review = rev['subject'].replace('<br>', ' ')
                if len(review) <= 3:
                    temp.append([5, '좋아요', ['좋아요'], [1.76], 9.1899])
                    continue
                score = rev['createDt']
                xai_before_text = []
                xai_value = []

                for sen in sss(review):
                    before_text, vs_1, _ , vs_2 = DNN_func(sen)
                    xai_before_text.extend(before_text)
                    value=[]
                    for w, v1, v2 in zip(before_text, vs_1, vs_2):
                        if len(w) == 0:
                            break
                        v0 = round((v1 + v2) / 2, 2)
                        value.append(v0)
                    xai_value.extend(value)

                temp.append([score, review, xai_before_text, xai_value,round(make_score2(make_score(sum(xai_value)/len(xai_value)))*10,1) ])

        return temp
    except:
        temp = []
        for i in range(10):
            temp.append(
                [5, '좋아요', ['좋아요'], [1.76], 9.1899])
        return temp


def Crawling_Naver(product_num, merchant_num, store,pageNo):
    try:
        if store == 'shopping':
            url = 'https://{}.naver.com/v1/reviews/paged-reviews?page={}&pageSize=10&merchantNo={}&originProductNo={}&sortType=REVIEW_RANKING'.format(
                store, pageNo, merchant_num, product_num)  # REVIEW_RANKING
        elif store == 'smartstore':
            url = 'https://{}.naver.com/i/v1/reviews/paged-reviews?page={}&pageSize=10&merchantNo={}&originProductNo={}&sortType=REVIEW_RANKING'.format(
                store, pageNo, merchant_num, product_num)  # REVIEW_RANKING
        elif store == 'brand':
            url = 'https://{}.naver.com/n/v1/reviews/paged-reviews?page={}&pageSize=10&merchantNo={}&originProductNo={}&sortType=REVIEW_RANKING'.format(
                store, pageNo, merchant_num, product_num)  # REVIEW_RANKING
        response = urlopen(url)
        json_data = json.load(response)['contents']
        temp = []
        for rev in json_data:
            if rev['reviewContent']:
                review = rev['reviewContent'].replace('/n', ' ')
                if len(review) <= 3:
                    temp.append([5, '좋아요', ['좋아요'], [1.76], 9.1899])
                    continue
                score = rev['createDate'].split('T')[0]
                score = score.replace("-",".")
                xai_before_text = []
                xai_value = []

                for sen in sss(review):
                    before_text, vs_1, _ , vs_2 = DNN_func(sen)
                    xai_before_text.extend(before_text)
                    value=[]
                    for w, v1, v2 in zip(before_text, vs_1, vs_2):
                        if len(w) == 0:
                            break
                        v0 = round((v1 + v2) / 2, 2)
                        value.append(v0)
                    xai_value.extend(value)

                temp.append([score, review, xai_before_text, xai_value,round(make_score2(make_score(sum(xai_value)/len(xai_value)))*10,1) ])

        return temp
    except:
        temp = []
        for i in range(10):
            temp.append(
                [5, '좋아요', ['좋아요'], [1.76], 9.1899])
        return temp

def sss(text):
    text = re.sub(r" {2,}", " ", hangul.sub(' ', text))
    end_char = ['요', '다', '죠']
    avoid_char = ['보다', '하려다', '하다', '려다']
    special_char = ['느림']
    new_sentences = []
    ts = text.split()
    start, end, flag = 0, 0, 0
    for i in range(len(ts)):
        if (len(ts[i]) >= 2 and ts[i][-1] in end_char and ts[i][-2:] not in avoid_char)\
                or ('ETN' in mecab.pos(ts[i])[-1][1]) or (ts[i][-2:] in special_char): # and mecab.pos(ts[i])[-1][1] != 'NNG'
            end = i
            new_sentences.append(' '.join(ts[start:end + 1]).strip())
            start = end + 1
            flag = 1
        else:
            if i == len(ts)-1:
                new_sentences.append(' '.join(ts[start:]).strip())
    if not flag and len(new_sentences) == 0:
        new_sentences.append(text)
    return new_sentences

def change_name(tt):
    tt = list(tt)
    for i in range(len(tt)):
        if tt[i] == '(' or tt[i] == '[':
            start = i
        elif tt[i] == ')' or tt[i] == ']':
            end = i
            tt[start:end + 1] = ['?' for i in range(len(tt[start:end + 1]))]
    tt = ''.join(tt)
    result_text = ''
    for i in tt.split():
        if '/' not in i:
            result_text = result_text + ' ' + i
    result_text = re.sub('[^0-9a-zA-Z가-힣\s]', '', result_text).strip()
    return result_text

def text_to_pandas(text):
    data = pd.DataFrame(text, columns=['score', 'review'])
    data = data.drop_duplicates(ignore_index=False).reset_index(drop=True)
    return data

# 분석과정
def preprocessing(review_data):
    for i in range(len(review_data)):
        review_data.loc[i, 'review'] = re.sub('[^0-9가-힣\s]', '', review_data.loc[i, 'review'])
    review_data = review_data.dropna().reset_index(drop=True)
    return review_data

def morphs_tokenizer(review_data):
    review_data_list = []
    for i in range(len(review_data)):
        rev = mecab.morphs(review_data.loc[i, 'review'])
        rev2 = [w for w in rev if mecab.pos(w)[0][1] not in stop_words]
        if rev2:
            review_data_list.append(rev2)
    return review_data_list

def morphs_pos(review_data):
    review_data_list = []
    for i in range(len(review_data)):
        rev = mecab.pos(review_data.loc[i, 'review'])  # mecab
        review_data_list.append(rev)
    return review_data_list

def return_nouns(review_data):
    nouns = []
    for i in range(len(review_data)):
        noun = mecab.pos(review_data.loc[i, 'review'])
        f_noun = [w for w, v in noun if v == 'NNG']  # or v=='VV' or v=='VX' or v='VA
        nouns.append(f_noun)
    return nouns

def count_noun(nouns):
    vocab = dict()
    for words in nouns:
        for word in words:
            if word not in vocab:
                vocab[word] = 1
            else:
                vocab[word] += 1
    vocab_sorted = sorted(vocab.items(), key=lambda x: x[1], reverse=True)
    return vocab_sorted

def check_vocab(t, review_data_list):
    t.fit_on_texts(review_data_list)
    vocab_size = len(t.word_index) + 1
    return vocab_size

def get_vector(word):
    if word in word2vec_model:
        return word2vec_model[word]
    else:
        return None

def return_keyword(review_data):
    review_data = pd.DataFrame(review_data, columns=['review']).reset_index(drop=True)
    review_data = preprocessing(review_data)  # 전처리
    review_data_list = morphs_pos(review_data)  # 형태소 토큰화
    nouns = return_nouns(review_data)  # 명사 추출
    vocab_sorted = count_noun(nouns)  # 명사 키워드
    check_vocab = vocab_sorted[:30]  # 20개 출력
    # JKS, JX_중요조사들
    josa = ['JKS', 'JX']  # 품사 중 조사에 대한 표현 저장 #+JKO, JKB, JKG, JKV, JKC, JC
    word_next_josa = {w: 0 for w, k in vocab_sorted}  # 단어 뒤에 조사가 붙는지에 대한 count를 저장하기 위한 딕셔너리
    for i in range(len(review_data_list)):
        for word, value in vocab_sorted:  # 저장된 단어들 호출
            for idx in range(len(review_data_list[i])):
                if word == review_data_list[i][idx][0]:
                    if idx + 1 < len(review_data_list[i]) and review_data_list[i][idx + 1][
                        1] in josa:  # 해당 단어의 다음에 조사가 나온다면
                        word_next_josa[word] += 1  # count 해줌

    word_josa_count = sorted(word_next_josa.items(), key=lambda x: x[1], reverse=True)[:20]  # count를 기준으로 sort 20개
    keyword_before = []
    for i in range(len(word_josa_count)):
        for j in range(len(check_vocab)):
            if word_josa_count[i][0] == check_vocab[j][0] and word_josa_count[i][
                1] > 1:  # 그냥 가장 많이 나온 단어들과 다음 단어가 조사가 나오는 단어들 중 을 선택
                keyword_before.append(word_josa_count[i][0])

    # 유사어 처리 및 불용어 처리(상품명, 제품, 상품,. ...)
    # 네이버 리뷰 20만개로 학습한 word2vec모델 load

    similar_word = []
    keyword = []
    for key in keyword_before:
        if key not in similar_word and key not in useless_NNG:  #
            keyword.append(key)
            try:
                result = word2vec_model.wv.most_similar(key)
                r = [w for w, v in result]
                similar_word.extend(r)
            except KeyError as e:
                pass

    return keyword, vocab_sorted

def vectors(sentence):
    # 각 문서에 대해서
    doc2vec = None
    count = 0
    for word in sentence:
        if word in list(word2vec_model.wv.index_to_key):
            count += 1
            # 해당 문서에 있는 모든 단어들의 벡터값을 더한다.
            if doc2vec is None:
                doc2vec = word2vec_model.wv.get_vector(word)
            else:
                doc2vec = doc2vec + word2vec_model.wv.get_vector(word)
    if doc2vec is not None:
        # 단어 벡터를 모두 더한 벡터의 값을 문서 길이로 나눠준다.
        doc2vec = doc2vec / count
    # 각 문서에 대한 문서 벡터 리스트를 리턴
    return doc2vec

def return_review_data(text):
    data = text_to_pandas(text)
    review_data = []
    for j in range(len(data)):
        for sentence in sss(data.loc[j, 'review']):
            review_data.append(sentence)
    review_data = pd.DataFrame(review_data, columns=['review']).reset_index(drop=True)
    review_data = preprocessing(review_data)  # 전처리
    nouns = return_nouns(review_data)  # 명사 추출
    vocab_sorted = count_noun(nouns)
    return review_data, vocab_sorted

def review_summarization(text):
    data = text_to_pandas(text)
    keyword, vocab_sorted = return_keyword(data)
    review_data = []
    for j in range(len(data)):
        for sentence in sss(data.loc[j, 'review']):
            review_data.append(sentence)
    review_data = pd.DataFrame(review_data, columns=['review']).reset_index(drop=True)
    review_data = preprocessing(review_data)  # 전처리
    review_data_list_pre = morphs_tokenizer(review_data)  # 형태소 토큰화
    count = {w: 0 for w in keyword}
    for i in range(len(review_data_list_pre)):
        for w in keyword:
            if w == review_data_list_pre[i][0]:
                count[w] += 1
    counted = sorted(count.items(), key=lambda x: x[1], reverse=True)[:25]
    keyword = [w for w, v in counted if v > 1]

    review_data_word = {}
    for word in keyword:
        review_data_list = []
        for i in range(len(review_data)):
            if word in review_data.loc[i, 'review']: # mecab.morphs(review_data.loc[i, 'review'])
                ws, vs_1, _, vs_2 = DNN_func(review_data.loc[i, 'review'])
                value = []
                for w, v1, v2 in zip(ws, vs_1, vs_2):
                    v = round((v1 + v2) / 2, 2)
                    value.append(v)
                if 2 < len(review_data.loc[i, 'review']) < 30:
                    temp_sent = [w for w in mecab.morphs(review_data.loc[i, 'review']) if
                                 w not in keyword]
                    if temp_sent:
                        doc2vec = vectors(temp_sent)
                        if doc2vec is not None:
                            review_data_list.append([i, review_data.loc[i, 'review'], doc2vec, round(make_score2(make_score(sum(value)/len(value)))*100,1)])  # [idx:]
        review_data_word[word] = review_data_list
    return review_data_word, keyword, vocab_sorted, review_data

def review_similarity_measurement(review_and_word):
    review_data_word={}
    each_keyword_ratio = {}
    for word in review_and_word:
        total = 0
        for i in range(len(review_and_word[word])):
            total += review_and_word[word][i][3]
        keyword_pos_neg_ratio = total/len(review_and_word[word])
        each_keyword_ratio[word] = keyword_pos_neg_ratio
        temp_list = []

        # ver3
        for i in range(len(review_and_word[word])):
            if float(keyword_pos_neg_ratio) - 15 <= review_and_word[word][i][3] <= float(keyword_pos_neg_ratio)+15:
                temp_list.append(review_and_word[word][i])
        review_data_word[word] = temp_list

    for word in review_data_word:
        doc_doc2vec = np.zeros(100, )
        for i in range(len(review_data_word[word])):
            doc_doc2vec = doc_doc2vec + review_data_word[word][i][2]
        doc2average = doc_doc2vec / len(review_data_word[word])
        review_data_word[word].append([np.nan, '리뷰들의 평균 벡터값입니다.', doc2average])
    document_embedding_list = {}

    for word in review_data_word:
        if len(review_data_word[word]) >= 2:
            document_embedding_list[word] = [review_data_word[word][0][2]]
            for i in range(1, len(review_data_word[word])):
                document_embedding_list[word].append(review_data_word[word][i][2])

    cosine_similarities = {}
    for word in document_embedding_list:
        cosine_similarities[word] = cosine_similarity(document_embedding_list[word], document_embedding_list[word])
    return cosine_similarities, review_data_word, each_keyword_ratio

def result_of_code(text):
    # 키워드 별 리뷰 요약 출력 (문장길이에 제한을 두어, 너무 긴 문장을 체택하지 않게 설정 _ 긴문장을 택하려는 경향이 있음)
    review_data_word, keyword, vocab_sorted, review_data = review_summarization(text)
    cosine_similarities, review_data_word, keyword_ratio = review_similarity_measurement(review_data_word)
    result = {}
    for word in cosine_similarities.keys():
        idx = list(cosine_similarities[word][-1]).index(sorted(cosine_similarities[word][-1], reverse=True)[1])
        rev = review_data_word[word][idx][1]
        if rev in result.values():  # 중복되는 문장에 대해선 그 다음 우선순위의 문장을 채택
            idx = list(cosine_similarities[word][-1]).index(sorted(cosine_similarities[word][-1], reverse=True)[2])
            rev = review_data_word[word][idx][1]
        result[word] = rev
    return result, keyword, vocab_sorted, review_data, keyword_ratio

def make_sim_word(keyword):
    similar_word = {}
    for word in keyword:
        try:
            similar_word[word] = [w for w, v in word2vec_model.wv.most_similar(word) if v >= 0.7]
        except:
            pass
    return similar_word

def keyword_in_review(temp_review, keyword):
    similar_word = make_sim_word(keyword)
    temp_review = re.sub('[^0-9가-힣\s]', '', temp_review)
    tokenized_review = mecab.morphs(temp_review)
    result_word = []

    # ver2
    for word in tokenized_review:
        for w in keyword:
            if w in word and w not in result_word:
                result_word.append(w)
        else:
            for key, sim_words in similar_word.items():
                if word in sim_words and key not in result_word:
                    result_word.append(key)


    #ver1
    # for word in tokenized_review:
    #     if word in keyword and word not in result_word:
    #         result_word.append(word)
    #     else:
    #         for key, sim_words in similar_word.items():
    #             if word in sim_words and key not in result_word:
    #                 result_word.append(key)
    return result_word

def similarity_and_major_similar_sentence(review_data, vocab_sorted, selected_review, rate):  # idx : 선택된 리뷰에서의 선택한 리뷰의 idx
    check_vo = [w for w, v in vocab_sorted if v >= 3 and w not in useless_NNG]
    most_N = ' '.join([w for w in check_vo]).strip()
    all_line_of_review = []
    for w, p in mecab.pos(selected_review):
        if (p == 'NNG' or p=='NNP') and w in most_N and w not in all_line_of_review :
            all_line_of_review.append(w)
    if len(all_line_of_review) == 0:
        return [], [], [], []

    all_review_of_same_word = []
    for i in range(len(review_data)):
        for word in all_line_of_review:
            if 2 < len(review_data.loc[i, 'review']) < 40 and word in review_data.loc[i, 'review'] and review_data.loc[
                i, 'review'] != selected_review:  # .split()
                all_review_of_same_word.append(review_data.loc[i, 'review'])
                break
    all_rev_of_same_word = []
    for rev in all_review_of_same_word:
        ws, vs_1, _ , vs_2 = DNN_func(rev)
        value = []
        for w, v1, v2 in zip(ws, vs_1, vs_2):
            if len(w) == 0:
                break
            v = round((v1 + v2) / 2, 2)
            value.append(v)
        if float(rate - 15) < make_score2(make_score(sum(value)/len(value)))*100 < float(rate + 15) and rev not in all_rev_of_same_word:
            all_rev_of_same_word.append(rev)

    if len(all_rev_of_same_word) == 0:
        return [], [], [], all_line_of_review

    all_rev_of_same_word.append(selected_review)
    for_similarity = []
    for i, r in enumerate(all_rev_of_same_word):
        if 2 < len(r) < 40 or i == len(all_rev_of_same_word) - 1:  # [idx:]
            doc2vec = vectors(r)
            for_similarity.append(doc2vec)  # [idx:]
    if len(for_similarity) < 2:
        return all_rev_of_same_word, [], []
    cosine_similarities_for_similarity = cosine_similarity(for_similarity, for_similarity)
    selected_line_with_similar_review_idx = [[i, r] for i, r in enumerate(cosine_similarities_for_similarity[-1])]
    result_sorted = sorted(selected_line_with_similar_review_idx, key=lambda x: x[1], reverse=True)
    result_same_sentences = []
    for index, val in result_sorted[1:]:
        if val >= 0.6:
            result_same_sentences.append(all_rev_of_same_word[index])
    return all_rev_of_same_word, result_same_sentences, result_sorted, all_line_of_review

def result_of_selected_review_s_same_reviews(selected_review, rate, review_data, vocab_sorted):
    all_review_of_same_word, result_same_sentences, result_sorted, same_word = similarity_and_major_similar_sentence(review_data, vocab_sorted, selected_review, rate)
    same = 0

    if not same_word:
        return [[['문장속',0],['비교할만한',0],['특성이',0],['없습니다!',0]]], 0

    if not result_same_sentences:
        return [[['유사한',0],['리뷰가',0],['없습니다!',0]]], 0

    checked_same_senteces = []
    for rss in result_same_sentences:
        each_rev = []
        for rs in rss.split():
            result_check_word_flag = []
            result_check_word_flag.append(rs)
            for sw in same_word:
                if sw in rs:
                    result_check_word_flag.append(1)
                    break
            else:
                result_check_word_flag.append(0)
            each_rev.append(result_check_word_flag)
        checked_same_senteces.append(each_rev)

    for idx, val in result_sorted[1:]:
        if val > 0.5:
            same += 1
    same_rate = round((same/len(result_sorted)) * 100,2)

    return checked_same_senteces, same_rate

def lets_do_crawling(site, product_num, url_src=None):
    if site == 1:
        url_basic = 'https://www.11st.co.kr/products/{}'.format(product_num)
        data = requests.get(url_basic, headers=headers)
        soup = BeautifulSoup(data.text, 'html.parser')
        category_path = soup.find('div', attrs={'class': 'c_product_category_path'}).find_all('em', attrs={
            'class': 'selected'})
        categories = ''
        for cate in category_path:
            if categories == '':
                categories = cate.text
            else:
                categories = categories + ', ' + cate.text

        product_name = re.sub('[/]', ' ', soup.find('h1', attrs={'class': 'title'}).text).strip()
        img_src = soup.find('div', attrs={'class': 'img_full'}).find('img')['src']
        price = soup.find('ul', attrs={'class': 'price_wrap'}).find('span', attrs={'class': 'value'}).text

        # review_len = soup.find('strong', attrs={'class': 'text_num'}).text
        # review_len = int(re.sub('[^0-9]', '', review_len))

        pool = Pool(4)
        func = partial(Crawling_11st,product_num)
        tem = pool.map(func, range(1,71))
        pool.close()
        pool.join()

        # text = [j for i in tem for j in i]

    elif site == 2:
        url_basic = url_src
        store = url_basic.split('//')[1].split('.')[0] # smartstore, brand, shopping
        data = requests.get(url_basic, headers=headers)
        soup = BeautifulSoup(data.text, 'html.parser')
        product_detail = soup.find_all('script')[1].text.split(',')

        for detail in product_detail:
            if '"payReferenceKey"' in detail:
                merchant_num = detail.split(':')[1].replace('"', '')
                break

        for detail in product_detail:
            if '"sellerImmediateDiscountPolicyNo"' in detail:
                product_num = re.sub('[^0-9]', '', detail.split(':')[2].replace('"', ''))
                break

        product_info = soup.find_all('script')[0].text.split(',')

        for info in product_info:
            if '"category"' in info:
                category = info.split(':')[1].replace('"', '')
                categories = ', '.join(category.split('>'))

        product_name = soup.find('h3', attrs={'class': '_3oDjSvLwq9 _copyable'}).text.strip()
        img_src = soup.find('div', attrs={'class': '_23RpOU6xpc'}).find('img')['src']
        price = soup.find('span', attrs={'class': '_1LY7DqCnwR'}).text
        # review_len = 할 수 있으면 하기

        pool = Pool(4)
        func = partial(Crawling_Naver, product_num, merchant_num, store)
        tem = pool.map(func, range(1, 71))
        pool.close()
        pool.join()


    text = [j for i in tem for j in i]
    tem_data = pd.DataFrame(text, columns=['score', 'review','xai_before_text','xai_value','xai_positive_negative'])
    cnt = 0
    for i in range(len(tem_data)):
        if tem_data.loc[i,'review'] == '좋아요':
            cnt+=1


    tem_data.drop_duplicates(['review'], inplace=True)
    if len(tem_data) > 500:
        tem_data = tem_data.sample(500)
    tem_data.reset_index(drop=True, inplace=True)
    review_len = len(tem_data)
    result, keyword, vocab_sorted, review_data, keyword_ratio = result_of_code([*map(lambda x : [x[0],x[1]], text)])

    return tem_data, product_name, img_src, price, review_len, categories, result, keyword, keyword_ratio
