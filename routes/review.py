import random
from flasgger import swag_from
from flask import jsonify, request, Blueprint
from elasticsearch import Elasticsearch
es = Elasticsearch(
    'ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25)

review = Blueprint("review", __name__, url_prefix="/")


@swag_from('./swagger/review.yml', methods=['POST'])
@ review.route('review', methods=['POST'])
def reviews():
    keyword = request.form.get("keyword", False)
    # keyword(사용자입력값)을 파라미터로 받아 keyword 가 "reviewLocation", "reviewTarget", "reviewTargetAddress", "reviewText"필드에있는지 elasticsearch 에 요청
    # last_year 작년 현재와 같은월, recent 최신순
    body_last_year = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "multi_match": {
                            "query": keyword,
                            "fields": ["reviewLocation", "reviewTarget", "reviewTargetAddress", "reviewText"]
                        }
                    },
                    # 작년 현재월로 변경예정 "reviewDate":  {"gte": "now/M-1y","lt": "now/M-1y+1M" }
                    {
                        "range": {
                            "reviewDate":  {
                                "gte": "now-2y/M",
                                "lt": "now/M"
                            }
                        }
                    }
                ],
                "must_not": {
                    "term": {
                        "reviewText": "정보없음"
                    }
                }
            }
        },
        # "sort": {"likes": "desc"},
        "size": 20,
        "_source": ["reviewText", "author", "rating", "skystate", "reviewTarget", "reviewSubject", "snow"],

    }
    body_recent = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "multi_match": {
                            "query": keyword,
                            "fields": ["reviewLocation", "reviewTarget", "reviewTargetAddress", "reviewText"]
                        }
                    }
                ],
                "must_not": {
                    "term": {
                        "reviewText": "정보없음"
                    }
                }
            }
        },
        # 최신순서대로 정렬
        "sort": [{"reviewDate": "desc"}],
        "size": 20,
        "_source": ["reviewText", "author", "rating", "skystate", "reviewTarget", "reviewSubject", "snow"],

    }

    last_year_es = es.search(
        index='siren-import-gimcheon-review', body=body_last_year)
    recent_es = es.search(
        index='siren-import-gimcheon-review', body=body_recent)

    res = {
        "recent": [],
        "last_year": []
    }
    # 작년,최근 elasticsearch데이터를 m_idx개만큼 받아 key(res["recent"],res["last_year"])에 담는다

    def reshaping(es_results, m_idx, key):
        for idx, i in enumerate(es_results['hits']['hits']):
            if idx > m_idx:
                break
            try:
                res[key].append(i["_source"])
            except:
                continue
    reshaping(recent_es, 20, "recent")
    reshaping(last_year_es, 20, "last_year")

    # 비,눈이 오는날 ,그렇지않은날(평범한날)에따라 무작위의 문장을 타이틀로 반환
    def making_title(type):
        snow_title = ['눈 오는날 가기좋은 %s', '눈이 오면 생각나는 %s', '눈 오는날 감상하기 좋은 %s',
                      '눈 오는날 더욱 느낌있는 %s', '눈오는날 갈만한 곳 %s 좋아요', '눈 오는 날 사진찍기 좋은 곳 %s']
        rain_title = ['비 오면 더 센치해지는 %s', '비 오면 더욱 이뻐지는 %s',
                      '비오는 날 감성 돋는 %s', '비 오는 날 갈만한 곳 %s', '%s 비오는 날 가기 좋은 곳']
        basic_title = ['산책하기 좋은 %s', '김천 가볼만한곳 %s', '가볼만한곳 %s 여행',
                       '%s로 세월을 감상하다', '%s 추천!', '아주 오랜만에 %s', '%s 다녀왔어요~', '%s 다녀오는길에', '효도여행 %s 다녀왔습니다.']
        if type == "rain":
            return random.choice(rain_title)
        elif type == "snow":
            return random.choice(snow_title)
        elif type == "normal":
            return random.choice(basic_title)

    # making_title 함수를 사용해 title을 추가하고 필요하지않는 key와 value를 pop
    def add_title(key):
        for i in key:
            # reviewSubject가 관광이면 비오는날,눈오는날,평범한날을 나눠 making_title함수실행후 불필요한 key,value pop
            if i["reviewSubject"] == "관광":
                if i["skystate"] == "비오는 날":
                    i["title"] = making_title("rain") % i["reviewTarget"]
                    i.pop("reviewSubject")
                    i.pop("skystate")
                    i.pop("reviewTarget")
                    i.pop("snow")
                elif i["snow"] == "1":
                    i["title"] = making_title("snow") % i["reviewTarget"]
                    i.pop("reviewSubject")
                    i.pop("skystate")
                    i.pop("reviewTarget")
                    i.pop("snow")
                else:
                    i["title"] = making_title("normal") % i["reviewTarget"]
                    i.pop("reviewSubject")
                    i.pop("skystate")
                    i.pop("reviewTarget")
                    i.pop("snow")
            # reviewSubject가 관광이아니면 reviewTarget이  itle
            else:
                i["title"] = i.pop("reviewTarget")
                i.pop("reviewSubject")
                i.pop("skystate")
                i.pop("snow")

    add_title(res["recent"])
    add_title(res["last_year"])

    # review keyword를 search_term index에 저장
    def search_terms():
        # es.indices.create(index="search_term")
        body = {
            "query": {
                "bool": {
                    "must": {
                        "term": {"search_term": keyword}
                    }
                }
            }
        }
        search_es = es.search(index='search_term', body=body)
        # 만약 값이 없다면 keyword 를 search_term index에 저장
        if search_es['hits']['total']['value'] == 0:
            doc = {
                "search_term": keyword,
                "count": 1
            }
            es.index(index="search_term", doc_type="_doc", body=doc)
        # search_term index에 이미 keyword가 있다면 count+1
        else:
            id = search_es['hits']['hits'][0]['_id']
            count = search_es['hits']['hits'][0]['_source']['count']
            source_to_update = {
                "doc": {
                    "search_term": keyword,
                    "count": count+1
                }
            }
            es.update(index="search_term", doc_type="_doc",
                      id=id, body=source_to_update)
    search_terms()
    return jsonify(res)