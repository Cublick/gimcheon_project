from flasgger import swag_from
from flask import jsonify,  Blueprint
from elasticsearch import Elasticsearch
from kiwipiepy import Kiwi

#
es = Elasticsearch('ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)

kiwi = Kiwi()

#최근 한달간 가장 Hot한 이슈 10곳 반환
graph_top = Blueprint("graph_top", __name__, url_prefix="/")

#김천의 관광지 리스트
queries = ["사명대사공원", "김천시립박물관", "직지사", "대웅전", "김천시립박물관", "직지문화공원", "연화지", "친환경생태공원",
           "김호중 소리길", "세계도자기박물관", "오봉저수지", "백수문학관", "빗내농악전수관", "출렁다리", "부항댐", "녹색미래과학관", "산내들오토캠핑장", "청솔수석박물관",
           "산내들패밀리어드벤처파크", "물소리생태숲", "옛날솜씨마을", "짚와이어", "이화만리녹색농촌체험마을", "경북수상레포츠", "방초정", "승마장", "무흘구곡", "시티투어", "나이트투어",
           "장전폭포", "증산 수도계곡", "인현왕후길", "불영산 청암사", "황악산", "수도암", "금오산", "수도산", "삼도봉", "치유의숲", "자산동 벽화마을", "무주군 대덕산", "종합스포츠타운",
           "포도홍보관", "문화예술회관", "김산항교", "황금시장", "김천역", "수도녹색숲모티길", "물문화관", "평화시장", "용화사", "계림사", "도동서원", "자동서원", "대성전", "춘천서원", "원계서원", "하로서원",
           "섬계서원", "경양서원", "용추폭포", "평화성당", "미륵암석조미륵불입상", "시립도서관", "황금성당", "봉곡사", "남산공원"]

this_month = {
    "gte": "now-4y-6M/M",
    "lt": "now-1M/M"
}

#관광지리스트(queries)와 기간(range)를 넣어 elasticsearch 집계형식으로 반환
def body(queries, range):
    queries_filterd = {}
    for i in queries:
        #각각의 관광지명이 postringText 필드에 있는지 쿼리
        queries_filterd[i] = {"term": {"postingText": i}}
    body_result = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "postingDate": range
                        }
                    }
                ]
            }
        },
        #위 의 쿼리 결과에대한 관광지를 집계형식으로 반환
        "aggs": {
            "rank": {
                "filters": {
                    "filters": queries_filterd
                }
            }
        },
        "size": 0
    }
    return body_result

# 관광지 리스트에서 1위로 뽑힌 키워드를 review Index에 날려 원하고자 하는 필드를 추출
def search_body(name):
    body = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "multi_match": {
                            "query": name,
                            "fields": ["reviewLocation", "reviewTarget", "reviewTargetAddress", "reviewText"]
                        }
                    }
                ],
                "must": {
                    "term": {
                        "reviewSubject": "관광"
                    }
                },
                "must_not": {
                    "term": {
                        "reviewText": "정보없음"
                    }
                }
            }
        },
        # 최신순서대로 정렬
        "sort": [{"reviewDate": "desc"}],
        "size": 30,
        "_source": ['author', 'rating', 'reviewTarget', 'reviewTargetAddress', 'reviewText']
    }
    return body

@swag_from('./swagger/graph_top.yml', methods=['POST'])
@graph_top.route('graph_top', methods=['POST'])
def graph_tops():
    this_month_list = es.search(index='siren-import-gimcheon-posting', body=body(queries, this_month)) # es 검색
    top_list = this_month_list['aggregations']['rank']['buckets'] # 관광지 카운트 추출

    # 관광지별 카운트 정리 (경북수상레포츠: 0)
    sort_list = {}
    for name, cnt in top_list.items():
        sort_list[name] = cnt['doc_count']

    tmp_name = sorted(sort_list.items(), key=lambda x: x[1], reverse=True)[:5]  # 탑1만 추출 하기위해 정렬 후 맨 처음 것만 사용

    import random

    ran = random.randrange(0, len(tmp_name))
    top_name = tmp_name[ran][0]

    review_result = es.search(index='siren-import-gimcheon-review-a',
                              body=search_body(top_name))['hits']['hits']  # 탑1 키워드를 reviewIndex에 검색

    review_list = []  # reviewText 저장
    rating_list = []
    text_tokenize = {  # NNG:명사 / VA: 동사 를 남기 위한 dict
       'NNG': {},
        'VA': {}
    }

    # 리뷰와 평점을 묶어서 저장하고, NNG, VA만을 추출
    for i in range(len(review_result)):
        if review_result[i]['_source']['reviewText'] not in review_list:
            review_list.append(review_result[i]['_source']['reviewText'])  # 리뷰 텍스트 저장
            rating_list.append(str(int(float(review_result[i]['_source']['rating']))) + '점')  # 리뷰 평점 저장

        tmp = kiwi.tokenize(review_result[i]['_source']['reviewText'])  # tokenize분리
        for t in tmp:
            if (t[1] == 'NNG' and t[0] != '곳') or ((t[1] == 'VA' and t[0] != '좋') and (t[1] == 'VA' and t[0] != '있')) or (t[1] == 'VA' and t[0] != '없'):
                if t[0] in text_tokenize[t[1]]:
                    text_tokenize[t[1]][t[0]] += 1
                else:
                    text_tokenize[t[1]][t[0]] = 0

    # 카운트 순으로 정렬하여 가장 높은 NNG, VA추출출
    POS = []
    for pos in text_tokenize:
        if pos == 'VA':
            ttm = sorted(text_tokenize[pos].items(), key=lambda x: x[1], reverse=True)
            for idx, t in enumerate(ttm):
                if len(t[0]) != 1:
                    POS.append(sorted(text_tokenize[pos].items(), key=lambda x: x[1], reverse=True)[idx][0])
                    break

        POS.append(sorted(text_tokenize[pos].items(), key=lambda x: x[1], reverse=True)[0][0])

    if POS[0] == '다리' and POS[1] == '그렇':
        POS[1] = '길'
    if POS[0] == '가까이' and POS[1] == '가볍':
        POS[0] = '단풍'
        POS[1] = '이쁘'
    if POS[0] == '' or POS[0] == ' ':
        POS[0] = '풍경'
    if POS[1] == '' or POS[1] == ' ':
        POS[1] = '이쁘'

    if POS[0] == '대웅전' and top_name == '대웅전':
        POS[0] = '사찰'
    if POS[0] == '옆' and top_name == '사명대사공원':
        POS[0] = '풍경'

    res = {
        'AILevel': 5,
        'Keyword': top_name,
        'sentence': POS[0] + '은(는)/이(가) ' + POS[1] + '다.',
        'reviews': review_list[:5],
        'ratings': rating_list[:5]
    }

    return jsonify(res)
