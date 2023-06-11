from flasgger import swag_from
from flask import jsonify,  Blueprint
from elasticsearch import Elasticsearch
from itertools import islice
es = Elasticsearch(
    'ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)

rank = Blueprint("rank", __name__, url_prefix="/rank")

#김천의 관광지 리스트
queries = ["사명대사공원", "김천시립박물관", "직지사", "대웅전", "김천시립박물관", "직지문화공원", "연화지", "친환경생태공원",
           "김호중 소리길", "세계도자기박물관", "오봉저수지", "백수문학관", "빗내농악전수관", "출렁다리", "부항댐", "녹색미래과학관", "산내들오토캠핑장", "청솔수석박물관",
           "산내들패밀리어드벤처파크", "물소리생태숲", "옛날솜씨마을", "짚와이어", "이화만리녹색농촌체험마을", "경북수상레포츠", "방초정", "승마장", "무흘구곡", "시티투어", "나이트투어",
           "장전폭포", "증산 수도계곡", "인현왕후길", "불영산 청암사", "황악산", "수도암", "금오산", "수도산", "삼도봉", "치유의숲", "자산동 벽화마을", "무주군 대덕산", "종합스포츠타운",
           "포도홍보관", "문화예술회관", "김산항교", "황금시장", "김천역", "수도녹색숲모티길", "물문화관", "평화시장", "용화사", "계림사", "도동서원", "자동서원", "대성전", "춘천서원", "원계서원", "하로서원",
           "섬계서원", "경양서원", "용추폭포", "평화성당", "미륵암석조미륵불입상", "시립도서관", "황금성당", "봉곡사", "남산공원"]

this_month = {
    "gte": "now-1y/M",
    "lt": "now/M"
}

last_month = {
    "gte": "now-1y-6M/M",
    "lt": "now-1y/M"
}

today = {
    "gte": "now-3y-6M/d",
    "lt": "now/d"
}

yesterday = {
    "gte": "now-3y-6M/d",
    "lt": "now-3y-1d/d"
}

#관광지리스트(queries)와 기간(range)를 넣어 elasticsearch 집계형식으로 반환
#3개월간 사용자의 입력값이 없을경우 top10,soaring에서 graph api 와 같은형식(posting 데이터 관광지 언급이 많은순)을 쓰고 3개월후 변경예정
def body(queries, range):
    queries_filterd = {}

    for i in queries:
         #각각의 관광지명이 postingText 필드에 있는지 쿼리
        queries_filterd[i] = {
            "term": {
                "postingText": i
            }
        }

    body_result = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "range": {
                            "postingDate":  range
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

#elasticsearch 쿼리 결과를 dic key:지명(음식점,숙박업명,관광지명)  , value:doc_count 대로 전처리합니다.
def reshaping(es, mod):
    reshaping_result = {}
    if mod == 1:
        for i, v in es["aggregations"]["rank"]["buckets"].items():
            reshaping_result[i] = es["aggregations"]["rank"]["buckets"][i]["doc_count"]
    elif mod == 2:
        for i in range(0, 10):
            try:
                reshaping_result[es["aggregations"]["rank"]["buckets"][i]['key']
                                 ] = es["aggregations"]["rank"]["buckets"][i]['doc_count']
            except:
                pass
    else:
        return
    #dic타입을 가진 reshaping_result 내림차순으로 정렬합니다.
    sorted_result = dict(sorted(reshaping_result .items(),
                                key=lambda item: item[1],
                                reverse=True))
    #reshaping_result값을 10개만 반환
    reshaping_result = dict(islice(sorted_result.items(), 10))

    return reshaping_result

#두개의 dic(최근한달결과,이전달결과)를 비교
#rank 순위 ,value 관광지, updown 변동순위
#변화가있다면 updown키에 "numner" 없다면 "-" 이전달에없었던 key값이라면 "new"반환
def comparison(present, past):
    result = []

    for pre_idx, (pre_name, pre_cnt) in enumerate(present.items()):
        if pre_name == '김천시 부곡동에서':
            pre_name = '김천시 부곡동'
        for pas_idx, (pas_name, pas_cnt) in enumerate(past.items()):
            object = {}
            if pre_idx == pas_idx and pre_name == pas_name:
                object['rank'] = pre_idx
                object['updown'] = '-'
                object['value'] = pre_name
                result.append(object)
                break

            elif pre_idx != pas_idx and pre_name == pas_name:
                object['rank'] = pre_idx
                object['updown'] = pas_idx - pre_idx
                object['value'] = pre_name
                result.append(object)
                break
        else:
            object['rank'] = pre_idx
            object['updown'] = 'new'
            object['value'] = pre_name
            result.append(object)

    return result



@swag_from('./swagger/rank_top.yml', methods=['POST'])
@rank.route('/top', methods=['POST'])
#지난달,최근한달 관광지 언급정도 데이터를 비교하여 dic형태로 반환합니다.
def top():

    this_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(queries, this_month)), 1)
    last_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(queries, last_month)), 1)

    top = comparison(this_month_es, last_month_es)

    return jsonify(top)


@swag_from('./swagger/rank_soaring.yml', methods=['POST'])
@rank.route('/soaring', methods=['POST'])
#어제,오늘 관광지 언급정도 데이터를 비교하여 dic형태로 반환합니다.
def soaring():
    today_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(queries, today)), 1)
    yesterday_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(queries, yesterday)), 1)

    soaring = comparison(today_es, yesterday_es)

    return jsonify(soaring)


@swag_from('./swagger/rank_restaurant.yml', methods=['POST'])
@rank.route('/restaurant', methods=['POST'])
#맛집순위
def restaurant():
    restaurant_list = []
    #review count 가 많은 음식점을 elasticsearch에 요청
    restaurant_body = {
        "query": {
            "match_all": {}
        },
        "sort": {"reviewCount": "desc"},
        "_source": ["name"],
        "size": 40
    }

    restaurant_es = es.search(
        index='siren-import-gimcheon-restaurant', body=restaurant_body)
    #~혁신점 등등 점으로 끝나는 데이터들은 프렌차이즈 집계에 방해되므로 제거
    for i in restaurant_es['hits']['hits']:
        name = i['_source']['name']
        if len(name.split(' ')) > 1 and name.split(' ')[-1][-1] == '점':
            restaurant_list.append(' '.join(name.split(' ')[:-1]))
        else:
            restaurant_list.append(name)
    #이번달 값과 최근한달 데이터를 가져와 비교
    this_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(restaurant_list, this_month)), 1)
    last_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(restaurant_list, last_month)), 1)

    restaurant = comparison(this_month_es, last_month_es)
    return jsonify(restaurant)


@swag_from('./swagger/rank_family.yml', methods=['POST'])
@rank.route('/family', methods=['POST'])
def family():
    #fmaily 필드에 가족여행이 들어간 데이터를 elasticsearch에 요청하여 전처리,비교후 반환
    def body_family(range):
        body_result = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "family": "가족여행"
                            }
                        },
                        {
                            "range": {
                                "reviewDate": range
                            }
                        }
                    ]
                }
            },
            "aggs": {
                "rank": {
                    "significant_text": {
                        "field": "reviewTarget"
                    }
                }
            },
            "size": 0
        }
        return body_result

    this_month_es = reshaping(es.search(
        index='siren-import-gimcheon-review-a', body=body_family(this_month)), 2)
    last_month_es = reshaping(es.search(
        index='siren-import-gimcheon-review-a', body=body_family(last_month)), 2)

    family = comparison(this_month_es, last_month_es)

    return jsonify(family)


@swag_from('./swagger/rank_insta.yml', methods=['POST'])
@ rank.route('/insta', methods=['POST'])
def insta():
    #insta like 필드 내림차순정렬 데이터를 elasticsearch에 요청하여 전처리,비교후 반환
    def body_insta(range):
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
            "sort": {"likes": "desc"},
            "aggs": {
                "rank": {
                    "terms": {
                        "field": "postingLocation",
                        #불필요한 결과값 예외처리
                        "exclude": ["Gimcheon", "[]", "김천", "gimcheon", "경상북도", "김천시", "구미", "김천혁신도시", "정보없음", '경상북도 김천', '마녀손톱']
                    }
                }
            },
            "size": 20
        }
        return body_result

    this_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body_insta(this_month)), 2)
    last_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body_insta(last_month)), 2)

    insta = comparison(this_month_es, last_month_es)

    return jsonify(insta)