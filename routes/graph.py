from flasgger import swag_from
from flask import jsonify,  Blueprint
from elasticsearch import Elasticsearch
from itertools import islice
es = Elasticsearch(
    'ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)

#최근 한달간 가장 Hot한 이슈 10곳 반환

graph = Blueprint("graph", __name__, url_prefix="/")

#김천의 관광지 리스트
queries = ["사명대사공원", "김천시립박물관", "직지사", "대웅전", "김천시립박물관", "직지문화공원", "연화지", "친환경생태공원",
           "김호중 소리길", "세계도자기박물관", "오봉저수지", "백수문학관", "빗내농악전수관", "출렁다리", "부항댐", "녹색미래과학관", "산내들오토캠핑장", "청솔수석박물관",
           "산내들패밀리어드벤처파크", "물소리생태숲", "옛날솜씨마을", "짚와이어", "이화만리녹색농촌체험마을", "경북수상레포츠", "방초정", "승마장", "무흘구곡", "시티투어", "나이트투어",
           "장전폭포", "증산 수도계곡", "인현왕후길", "불영산 청암사", "황악산", "수도암", "금오산", "수도산", "삼도봉", "치유의숲", "자산동 벽화마을", "무주군 대덕산", "종합스포츠타운",
           "포도홍보관", "문화예술회관", "김산항교", "황금시장", "김천역", "수도녹색숲모티길", "물문화관", "평화시장", "용화사", "계림사", "도동서원", "자동서원", "대성전", "춘천서원", "원계서원", "하로서원",
           "섬계서원", "경양서원", "용추폭포", "평화성당", "미륵암석조미륵불입상", "시립도서관", "황금성당", "봉곡사", "남산공원"]
this_month = {
    "gte": "now-1y-1M/M",
    "lt": "now-1y+2M/M"
}

last_month = {
    "gte": "now/M-1y-2M",
    "lt": "now/M-1y"
}

today = {
    "gte": "now-1d/d",
    "lt": "now/d"
}

yesterday = {
    "gte": "now-1d/d-1d",
    "lt": "now/d-1d"
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


def reshaping(es, mod):
    reshaping_result = {}
    if mod == 1:
        for i, v in es["aggregations"]["rank"]["buckets"].items():
            reshaping_result[i] = es["aggregations"]["rank"]["buckets"][i]["doc_count"]
    elif mod == 2:
        for i in range(0, 10):
            reshaping_result[es["aggregations"]["rank"]["buckets"][i]['key']
                             ] = es["aggregations"]["rank"]["buckets"][i]['doc_count']
    else:
        return
    # dict타입을 가진 reshaping_result 내림차순으로 정렬합니다.
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

    for idx, k in enumerate(present.items()):
        for last_idx, last_k in enumerate(past.items()):
            object = {}
            if k[0] == last_k[0] and idx != last_idx:
                updown = last_idx - idx
                object['rank'] = idx
                object['value'] = k[0]
                object['updown'] = updown
                result.append(object)
                break
            elif k[0] == last_k[0] and idx == last_idx:
                object['rank'] = idx
                object['value'] = k[0]
                object['updown'] = '-'
                result.append(object)
                break
            else:
                object['rank'] = idx
                object['value'] = k[0]
                object['updown'] = 'new'
                result.append(object)
                break
    return result




@swag_from('./swagger/graph.yml', methods=['POST'])
@graph.route('graph', methods=['POST'])
def graphs():
    #posting index에 최근 한달동안 가장많이 언급된 데이터를 key:value 값으로 반환
    this_month_es = reshaping(es.search(
        index='siren-import-gimcheon-posting', body=body(queries, this_month)), 1)

    return jsonify(this_month_es)
