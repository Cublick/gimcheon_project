from flasgger import swag_from
from flask import jsonify, request, Blueprint
from elasticsearch import Elasticsearch
es = Elasticsearch(
    'ec2-54-180-112-236.ap-northeast-2.compute.amazonaws.com:9220', maxsize=25) # 서버주소

autocomplete = Blueprint('autocomplete', __name__, url_prefix='/')

@swag_from('./swagger/autocomplete.yml', methods=['POST'])
@autocomplete.route('autocomplete', methods=['POST'])
def autocompletes():
    keyword = request.form.get('keyword', False) # 사용자가 입력한 검색어

    body = [
        # search 할 음식점 5개를 찾기 위한 query
        {
            "index": "siren-import-gimcheon-restaurant" # search할 index
        },
        {
            "query": {
                "bool": {
                    "must": [ # query 필수조건, 결과 참인 것만 추출
                        {
                            "match": { # jaso_tokenizer 적용으로 keyword 값이 자음만 들어와도 결과 값을 반환
                                "name.jaso": { # jaso : 자음 모음으로 분리하여 검색 (초성검색 가능),
                                    "query": keyword, # keyword : 사용자가 입력한 값
                                    "analyzer": "suggest_search_analyzer" # jaso analyzer 이름
                                }
                            }
                        }
                    ],
                    "should": [ # 조건에 해당하는 결과 중 정확도를 높여 점수 높임
                        {
                            "match": { # must 결과 값을 넣어 keyword와 같은 grams를 갖은 데이터를 우선반환
                                "name.ngram": { # ngram: 원하는 숫자만큼 토큰을 잘라서 검색 가능하도록
                                    "query": keyword,
                                    "analyzer": "my_ngram_analyzer" # n-gram analyzer 이름
                                }
                            }
                        }
                    ]
                }
            },
            "size": 5,
            "_source": ["name"]
        },
        # 검색바에서 숙박점 5개를 찾기 위한 query
        {
            "index": "siren-import-gimcheon-accommodation"
        },
        {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "name.jaso": {
                                    "query": keyword,
                                    "analyzer": "suggest_search_analyzer"
                                }
                            }
                        }
                    ],
                    "should": [
                        {
                            "match": {
                                "name.ngram": {
                                    "query": keyword,
                                    "analyzer": "my_ngram_analyzer"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 5,
            "_source": ["name"]
        },
        # 검색바에서 리뷰 5개를 찾기 위한 query
        {
            "index": "siren-import-gimcheon-review"
        },
        {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "reviewText.jaso": {
                                    "query": keyword,
                                    "analyzer": "suggest_search_analyzer"
                                }
                            }
                        }
                    ],
                    "should": [
                        {
                            "match": {
                                "reviewText.ngram": {
                                    "query": keyword,
                                    "analyzer": "my_ngram_analyzer"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 5,
            "_source": ["reviewText"]
        },
        {
            "index": "siren-import-gimcheon-touristspot"
        },
        {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "name.jaso": {
                                    "query": keyword,
                                    "analyzer": "suggest_search_analyzer"
                                }
                            }
                        }
                    ],
                    "should": [
                        {
                            "match": {
                                "name.ngram": {
                                    "query": keyword,
                                    "analyzer": "my_ngram_analyzer"
                                }
                            }
                        }
                    ]
                }
            },
            "size": 5,
            "_source": ["name"]
        }
    ]

    autocomplete_es = es.msearch(body=body) # msearch를 통해 query를 한번에 검색

    res = {
        "restaurants": [],
        "accommodation": [],
        "review": [],
        "touristspot": []
    }

    for idx in range(0, 4):
        if idx == 0: # restaurants 결과값
            for i in autocomplete_es["responses"][idx]['hits']['hits']:
                res["restaurants"].append(i["_source"]["name"])
        elif idx == 1: # accommodation 결과값
            for i in autocomplete_es["responses"][idx]['hits']['hits']:
                res["accommodation"].append(i["_source"]["name"])
        elif idx == 2: # review 결과값
            for i in autocomplete_es["responses"][idx]['hits']['hits']:
                res["review"].append(i["_source"]["reviewText"])
        elif idx == 3: # touristspot 결과값
            for i in autocomplete_es["responses"][idx]['hits']['hits']:
                res["touristspot"].append(i["_source"]["name"])

    # 중복제거
    result = {
        'touristspot': [],
        'accommodation': [],
        'restaurants': [],
        'review': []
    }

    for r in res:
        for i in res[r]:
            if r == 'review': # 리뷰는 중복으로 작성할 수 있으므로 패스
                result[r].append(i)
            elif i not in result[r]: # 관광지, 숙박, 음식점의 명 중복제거
                result[r].append(i)

    return jsonify(result)